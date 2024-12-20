#!/usr/bin/env python3
from typing import Union, Any, Callable, Type, Optional, TypeVar, Generic, Iterable

import ns, sys, pathlib

args = sys.argv[1:]

pathHere = pathlib.Path(__file__).parent

if len(args) == 0:
    print('Missing source file')
    exit(1)
    
frames_cache = {}

def consume_ns_arg(arg:str) -> bool:
    if arg in args and ('--' not in args or args.index(arg) < args.index('--')):
        args.pop(args.index(arg))
        return True
    return False

def explore(tree) -> str:
    if isinstance(tree,(ns.Node,ns.FunctionParameter)):
        s = '\x1b[1;7m'+tree.__class__.__name__+'\x1b[m { '
        props = {}
        props.update(dict(map(lambda k:(k,getattr(tree,k) if hasattr(tree,k) else None),tree.__annotations__)))
        if len(props) > 1: s += '\n'
        for k,v in props.items():
            t = ''
            if hasattr(tree,k):
                r = explore(v).replace('\n','\n  ')
                t += '\x1b[36m'+k+'\x1b[39m : '+r+'\x1b[39m'
            else:
                r = ''
                t += '\x1b[90m'+k+'\x1b[39m'
            if len(props) == 1 and '\n' not in r:
                s += t+' '
            else:
                if len(props) == 1:
                    s += '\n'
                s += '  '+t+'\n'
        return s+'}'
    elif isinstance(tree,list):
        s = '['
        if len(tree): s += '\n'
        for v in tree:
            s += '  '+explore(v).replace('\n','\n  ')+'\x1b[39m\n'
        return s+']'
    elif isinstance(tree,set):
        s = '(set)['
        if len(tree): s += '\n'
        for v in tree:
            s += '  '+explore(v).replace('\n','\n  ')+'\x1b[39m\n'
        return s+']'
    elif isinstance(tree,tuple):
        s = '( '
        for i,v in enumerate(tree):
            s += explore(v).replace('\n','\n  ')+'\x1b[39m'+(', ' if i < len(tree)-1 else '')
        s += ' )'
        return s
    elif isinstance(tree,ns.Token):
        return str(tree)
    elif isinstance(tree,str):
        return '\x1b[32m'+repr(tree)+'\x1b[39m'
    elif isinstance(tree,(int,float,bool)):
        return '\x1b[33m'+repr(tree)+'\x1b[39m'
    elif tree == None:
        return '\x1b[90m'+repr(tree)+'\x1b[39m'
    else:
        return '\x1b[31m'+repr(tree)+'\x1b[39m'

class RewindReturn(BaseException):
    """
    Raised to return from a function
    """
    
    value: 'NSValue'
    
    def __init__(self, value: 'NSValue'):
        self.value = value
        
class RewindBreak(BaseException):
    """
    Raised to break out of a loop
    """
    
    value: 'NSValue'
    
    def __init__(self, value: 'NSValue'):
        self.value = value
        
class RewindContinue(BaseException):
    """
    Raised to continue a loop
    """
    
    value: 'NSValue'
    
    def __init__(self, value: 'NSValue'):
        self.value = value

class FunctionException(BaseException):
    """
    Raised from a Python NSFunction to signal an error
    """
    
    message: Union[str,None]
    
    def __init__(self, message: str = None):
        self.message = message
    
class NSEException(BaseException):
    """
    Holds data about a runtime error
    """
    
    message : str
    l       : int
    c       : int
    s       : int
    source  : ns.Source
    
    def __init__( self, message:str, l:int, c:int, s:int, source:ns.Source ):
        self.message = message
        self.l = l
        self.c = c
        self.s = s
        self.source = source
        
    def errname( self ) -> str:
        return 'Runtime Error'
        
    def __str__( self ) -> str:
        rline = self.source.body.splitlines(False)[self.l]
        line = rline.lstrip()     # removes all indent
        dl = len(rline)-len(line) # computes the shift caused by the indent
        return '\x1b[31;1m%s\x1b[22;39m (\x1b[36m%s:%d:%d\x1b[39m):\n  %s\n\n  %s\n  %s' % (self.errname(),self.source.name,self.l+1,self.c+1,self.message.replace('\n','\n  '),line[:self.c-dl]+'\x1b[33m'+line[self.c-dl:self.c-dl+self.s]+'\x1b[39m'+line[self.c-dl+self.s:],' '*(self.c-dl)+'^'+'~'*(self.s-1))
    
    @staticmethod
    def fromNode( msg:str, node:ns.Node ) -> 'NSEException':
        token = node.tokens.tokens[node.i]
        return NSEException(msg, token.l, token.c, len(token.t), token.s)
    
    @staticmethod
    def fromToken( msg:str, token:ns.Token ) -> 'NSEException':
        return NSEException(msg, token.l, token.c, len(token.t), token.s)

class NSFunction:
    
    class Arguments:
        
        args   : list['NSValue']
        kwargs : dict[str,'NSValue']
        fn     : 'NSValue'
        bound  : Optional['NSValue']
        
        def __init__( self, args: list['NSValue'], kwargs: dict[str,'NSValue'] , fn: 'NSValue', bound: Optional['NSValue'] = None):
            self.args = args
            self.kwargs = kwargs
            self.fn = fn
            self.bound = bound
    
    def __init__( self ):
        pass
    
    def call( self, ctx: 'NSEContext', frame: 'NSEFrame', args: Arguments ) -> 'NSValue':
        raise RuntimeError('That should not have happened')
    
class NSFunctionNative(NSFunction):
    
    callback : Callable[['NSEContext',NSFunction.Arguments],'NSValue']
    
    def __init__( self, callback: Callable[['NSEContext',NSFunction.Arguments],'NSValue'] ):
        super().__init__()
        self.callback = callback
        
    def call( self, ctx: 'NSEContext', frame: 'NSEFrame', args: NSFunction.Arguments ) -> 'NSValue':
        return NSValue.sanitize(self.callback(ctx,frame,args))
        
class NSFunctionCode(NSFunction):
    
    func  : ns.NodeFunction
    frame : 'NSEFrame'
    
    def __init__( self, func: ns.NodeFunction, frame: 'NSEFrame' ):
        super().__init__()
        self.func = func
        self.frame = frame
        
    def call( self, ctx: 'NSEContext', frame: 'NSEFrame', args: NSFunction.Arguments ) -> 'NSValue':
        mapping = dict((param.name,None) for param in self.func.pararameters)
        for name, arg in args.kwargs.items():
            if name in mapping:
                mapping[name] = arg
            else:
                raise FunctionException('Argument %s does not exist in this function'%(name,))
        for arg in args.args:
            found = False
            for name, val in mapping.items():
                if val == None:
                    mapping[name] = arg
                    found = True
                    break
            if not found:
                raise FunctionException('Unexpected extra argument')
        for name, val in mapping.items():
            if val == None:
                mapping[name] = NULL()
        frame = self.frame(mapping)
        frame.vars.new('self',args.bound or NULL())
        if self.func.body == None:
            return NULL()
        else:
            try:
                return ctx.exec(self.func.body,frame)
            except RewindReturn as ret:
                return ret.value

class NSKind:

    class Class(): pass
    class Trait(): pass
    class Null(): pass
    class Ref(): pass

def impl_trait( target: 'NSValue', trait: 'NSValue' ):
    if not isinstance(trait,NSValue) or trait.type != NSKind.Trait:
        raise TypeError('Trait argument has to be an NSValue Trait')
    if not isinstance(target,NSValue) or target.type != NSKind.Class:
        raise TypeError('Traits can only be applied on NSValue Class')
    def wrapper( impl ):
        cls = NSValue.make_class(impl)
        target.data['__class']['trait'][trait] = cls
        return impl
    return wrapper

class NSValue:
    
    type : Optional['NSValue']
    data : dict
    
    conversions = {
        str:   lambda v: NSValue.String(v),
        int:   lambda v: NSValue.Number(v),
        float: lambda v: NSValue.Number(v),
        bool:  lambda v: NSValue.Boolean(v)
    }
    
    conversions_weak = {
        Callable: lambda v: NSValue.Function(v)
    }
    
    _late_types = []
    @staticmethod
    def _latetype():
        for v in NSValue._late_types:
            v.type = eval(v.type)
        del NSValue._late_types
        del NSValue._latetype
    @staticmethod
    def _latevalue( data: dict, type: Optional[str] ):
        if hasattr(NSValue,'_late_types'):
            f = NSValue(data,type)
            NSValue._late_types.append(f)
            return f
        return NSValue(data,eval(type))
    
    def __init__( self, data: dict, type: Optional['NSValue'] = None, props: Optional[dict] = None ):
        self.data = data
        self.props = props or {}
        self.type = type
        
    def get( self, prop: str, searchInstance: Optional[bool] = True, searchClass: Optional[bool] = False ) -> 'NSValue':
        if self.type == NSKind.Null:
            return NULL()
        if self.type == NSKind.Ref:
            return self.data.get(prop, searchInstance, searchClass)
        if searchInstance:
            return self.props.get(prop, NULL())
        if searchClass:
            return self.type.props.get(prop, NULL())
        return NULL()
    
    S = TypeVar('S',bound='NSValue')
    def set( self, prop: str, value: S ) -> S:
        if self.type == NSKind.Ref:
            return self.data.set(prop, value)
        if self.type in (NSKind.Null,NSKind.Class,NSKind.Trait):
            pass
        else:
            self.props[prop] = value
        return value
        
    @staticmethod
    def sanitize( value: Any ) -> 'NSValue':
        if value == None:
            return NULL()
        if type(value) == NSValue:
            return value
        c = NSValue.conversions.get(type(value))
        if c:
            return c(value)
        for t,c in NSValue.conversions_weak.items():
            if isinstance(value,t):
                return c(value)
        raise ValueError(value,'Unsupported type')
    
    @staticmethod
    def make_class( pre: Type ) -> 'NSValue':
        props = {}
        trait = getattr(pre,'__trait') if hasattr(pre,'__trait') else {}
        
        if pre != None:
            for p,v in pre.__dict__.items():
                if p.startswith('_'): continue
                props[p] = NSValue.sanitize(v)
        
        return NSValue({
            '__class' : {
                'class' : pre,
                'super' : pre.__super if hasattr(pre,'_super') else [],
                'trait' : trait
            }
        },NSKind.Class,props)
        
    @staticmethod
    def create_trait( methods ) -> 'NSValue':
        return NSValue({
            'methods': methods
        },NSKind.Trait)
        
    @staticmethod
    def make_trait( target ):
        if not isinstance(target,NSValue) or target.type != NSKind.Trait:
            raise TypeError('make_trait must be called with a trait')
        class wrapper:
            def __init__( self, trait ):
                for m in target.data['methods']:
                    if not hasattr(trait,m) or not callable(getattr(trait,m)):
                        raise TypeError('Implementation is missing method %s'%(repr(m),))
                self.trait = trait
            def __set_name__( self, owner, name ):
                if not hasattr(owner,'__trait'):
                    setattr(owner,'__trait',{})
                getattr(owner,'__trait')[target] = NSValue.make_class(self.trait)
        return wrapper
    
    def instantiate( self, *args, **kwargs ) -> 'NSValue':
        if self.type == NSKind.Class:
            val = NSValue({},self,{})
            cls = self.data['__class']['class']
            if hasattr(cls,'__init__'):
                getattr(cls,'__init__')(val,*args,**kwargs)
            return val
        else:
            raise ValueError('Only Class is instantiable')
        
    def get_trait( self, trait: 'NSValue' ) -> Union['NSValue',None]:
        cls: dict = self.data.get('__class',None) if isinstance(self.data,dict) else None
        if not cls and isinstance(self.type,NSValue):
            cls = self.type.data.get('__class',None)
        if not cls:
            return None
        return cls.get('trait',{}).get(trait,None)

    def get_trait_attribute( self, trait: 'NSValue', name: str ) -> Union['NSValue',None]:
        t = self.get_trait(trait)
        if not t:
            return None
        return t.props.get(name,None)
    
    def get_trait_method( self, trait: 'NSValue', name: str ) -> Union[NSFunction,None]:
        attr = self.get_trait_attribute(trait,name)
        if not attr or attr.type != NSTypes.Function:
            return None
        return attr.data.get('__function',{}).get('func',None)
    
    @staticmethod
    def Function( callback: Callable[['NSEContext','NSFunction.Arguments'],'NSValue'] ) -> 'NSValue':
        return NSValue._latevalue({'__function':{'func':NSFunctionNative(callback),'bound':None}},'NSTypes.Function')
    
    @staticmethod
    def String( value: str ) -> 'NSValue':
        return NSValue._latevalue(value,'NSTypes.String')
    
    @staticmethod
    def Number( value: Union[int,float] ) -> 'NSValue':
        return NSValue._latevalue(float(value),'NSTypes.Number')
    
    @staticmethod
    def Boolean( value: Any ) -> 'NSValue':
        return NSValue._latevalue(bool(value),'NSTypes.Boolean')
    
    @staticmethod
    def Array( items: list['NSValue'] ) -> 'NSValue':
        return NSValue._latevalue({'items':items},'NSTypes.Array')
    
    @staticmethod
    def BasicDecorator( dec: Callable[['NSValue',list['NSValue'],ns.DecoratableNode],Any] ) -> 'NSValue':
        # def apply( value: NSValue, args: list[NSValue], node: ns.DecoratableNode, dec: ns.NodeDecorator  ):
        #     dec(value,args,node)
        return NSValue._latevalue({'post':dec},'NSTypes.Decorator')

class NSTraits:
    
    ToString = NSValue.create_trait(('toString',))
    Iterator = NSValue.create_trait(('items',))
    Copy = NSValue.create_trait(('copy',))

    class Op:
        
        Add = NSValue.create_trait(('add',))
        Sub = NSValue.create_trait(('sub',))
        Mul = NSValue.create_trait(('mul',))
        Div = NSValue.create_trait(('div',))
        
        Inc = NSValue.create_trait(('inc',))
        Dec = NSValue.create_trait(('dec',))
        
        Eq = NSValue.create_trait(('eq',))
        Gt = NSValue.create_trait(('gt',))
        Lt = NSValue.create_trait(('lt',))
    
ellipsis = type[Ellipsis]
        
def _check_bound_to(args: 'NSFunction.Arguments', target: NSValue):
    if not args.bound:
        raise FunctionException('Unbound method call')
    elif args.bound.type != target:
        raise FunctionException('Call to method bound to wrong type')
    
def _check_called_with(args: 'NSFunction.Arguments', target: Union[tuple[Union[NSValue,ellipsis]],list[tuple[Union[NSValue,ellipsis]]]]):
    target = [target] if isinstance(target, tuple) else target
    for alt in target:
        for i, t in enumerate(alt):
            if i+1 < len(alt) and isinstance(alt[i+1], ellipsis):
                for j in range(i,len(args.args)):
                    if args.args[j].type != t:
                        raise FunctionException('TBD#1')
            else:
                if i >= len(args.args):
                    raise FunctionException('TBD#2')
                elif args.args[i].type != t:
                    raise FunctionException('TBD#3')
                
def _check_args(args: 'NSFunction.Arguments', bound: NSValue = None, arguments: Union[tuple[Union[NSValue,ellipsis]],list[tuple[Union[NSValue,ellipsis]]]] = None):
    if bound != None: 
        _check_bound_to(args, bound)
    if arguments != None: 
        _check_called_with(args, arguments)
        
class util:
    
    @staticmethod
    def assign_ref(target: NSValue, value: NSValue):
        target.data = value.data
        target.props = value.props
        target.type = value.type
        
    @staticmethod
    def copy(ctx: 'NSEContext', frame: 'NSEFrame', value: NSValue):
        if value.type == NSKind.Null:
            return NULL()
        copy = value.get_trait_method(NSTraits.Copy, 'copy')
        return copy.call(ctx, frame, NSFunction.Arguments([],{},copy,value)) if copy else value

def assign(node: ns.Node, value: NSValue, frame: 'NSEFrame', ctx: 'NSEContext'):
    if isinstance(node, ns.NodeName):
        frame.vars.set(node.name, value)
        return
    elif isinstance(node, ns.NodeAccessDot):
        ctx.exec(node.node,frame).set(node.prop, value)
        return
    elif isinstance(node, ns.NodeOperatorPrefix) and node.op.t == '*':
        target = ctx.exec(node.value, frame, False)
        if target.type != NSKind.Ref:
            raise NSEException.fromToken('Can\'t dereference `%s`'%(toNSString(ctx,frame,value.type),),node.op)
        util.assign_ref(target.data,value)
        return
    elif isinstance(node, ns.NodeExpression):
        assign(node.expression, value, frame, ctx)
        return
    raise NSEException.fromNode('Assignment to \'%s\' is not currently supported'%(type(node).__name__,),node)

# TODO: Implement constructor for all of them

class NSTypes:
    @NSValue.make_class
    class Module:
        pass

    @NSValue.make_class
    class Function:
        @NSValue.make_trait(NSTraits.Copy)
        class __trait_Copy:
            def copy(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Function, ())
                return NSValue(args.bound.data,args.bound.type)
        
        def bind(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments') -> NSValue:
            _check_args(args, NSTypes.Function)
            f = args.bound
            b = args.args[0] if len(args) > 0 else NULL()
            return NSValue({'__function':{'func':f.data['__function'].get('func',None),'bound':b}},f.type,f.props|{'bound':b})

    @NSValue.make_class
    class String:
        @NSValue.make_trait(NSTraits.Copy)
        class __trait__Copy:
            def copy(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.String, ())
                return NSValue.String(args.bound.data)
        
        @NSValue.make_trait(NSTraits.Op.Add)
        class __trait__Add:
            def add(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.String, (NSTypes.String,))
                other, = args.args
                return NSValue.String(args.bound.data+other.data)
            
        @NSValue.make_trait(NSTraits.Op.Mul)
        class __trait__Mul:
            def mul(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.String, (NSTypes.Number,))
                other, = args.args
                return NSValue.String(args.bound.data*other.data)

        @NSValue.make_trait(NSTraits.Op.Lt)
        class __trait__Lt:
            def lt(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.String, (NSTypes.String,))
                other, = args.args
                return TRUE() if args.bound.data<other.data else FALSE()
            
        @NSValue.make_trait(NSTraits.Op.Gt)
        class __trait__Gt:
            def gt(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.String, (NSTypes.String,))
                other, = args.args
                return TRUE() if args.bound.data>other.data else FALSE()
            
        @NSValue.make_trait(NSTraits.Op.Eq)
        class __trait__Eq:
            def eq(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.String, (NSTypes.String,))
                other, = args.args
                return TRUE() if args.bound.data==other.data else FALSE()

        @NSValue.make_trait(NSTraits.Op.Dec)
        class __trait__Dec:
            def dec(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.String, ())
                return NSValue.String(args.bound.data[:-1])

    @NSValue.make_class
    class Number:
        @NSValue.make_trait(NSTraits.Copy)
        class __trait__Copy:
            def copy(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, ())
                return NSValue.Number(args.bound.data)
        
        @NSValue.make_trait(NSTraits.Op.Lt)
        class __trait__Lt:
            def lt(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, (NSTypes.Number,))
                other, = args.args
                return TRUE() if args.bound.data<other.data else FALSE()
            
        @NSValue.make_trait(NSTraits.Op.Gt)
        class __trait__Gt:
            def gt(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, (NSTypes.Number,))
                other, = args.args
                return TRUE() if args.bound.data>other.data else FALSE()
            
        @NSValue.make_trait(NSTraits.Op.Add)
        class __trait__Add:
            def add(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, (NSTypes.Number,))
                other, = args.args
                return NSValue.Number(args.bound.data+other.data)
            
        @NSValue.make_trait(NSTraits.Op.Sub)
        class __trait__Sub:
            def sub(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, (NSTypes.Number,))
                other, = args.args
                return NSValue.Number(args.bound.data-other.data)

        @NSValue.make_trait(NSTraits.Op.Mul)
        class __trait__Mul:
            def mul(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, (NSTypes.Number,))
                other, = args.args
                return NSValue.Number(args.bound.data*other.data)
            
        @NSValue.make_trait(NSTraits.Op.Div)
        class __trait__Div:
            def div(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, (NSTypes.Number,))
                other, = args.args
                return NSValue.Number(args.bound.data/other.data)

        @NSValue.make_trait(NSTraits.Op.Eq)
        class __trait__Eq:
            def eq(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, (NSTypes.Number,))
                other, = args.args
                return NSValue.Boolean(args.bound.data==other.data)
            
        @NSValue.make_trait(NSTraits.Op.Inc)
        class __trait__Inc:
            def inc(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, ())
                return NSValue.Number(args.bound.data+1)
            
        @NSValue.make_trait(NSTraits.Op.Dec)
        class __trait__Dec:
            def dec(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Number, ())
                return NSValue.Number(args.bound.data-1)
            
    @NSValue.make_class
    class Array:
        def __init__( self: NSValue ):
            pass
        
        def push( ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments' ) -> NSValue:
            _check_args(args, NSTypes.Array)
            args.bound.data['items'].append(args.args[0] if len(args.args) >= 1 else NULL())
            return NULL()
        
        def pop( ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments' ) -> NSValue:
            _check_args(args, NSTypes.Array, ())
            return args.bound.data['items'].pop() if len(args.bound.data['items']) else NULL()
        
        @NSValue.make_trait(NSTraits.Op.Add)
        class __trait__Add:
            def add(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Array, (NSTypes.Array,))
                other, = args.args
                return NSValue.Array(args.bound.data['items']+other.data['items'])
                
    @NSValue.make_class
    class Boolean:
        @NSValue.make_trait(NSTraits.Copy)
        class __trait__Copy:
            def copy(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Boolean, ())
                return NSValue.Boolean(args.bound.data)
    
    @NSValue.make_class
    class Logic:
        def __init__( self: NSValue, variant: int ):
            self.data['parents'] = []
            self.data['children'] = []
            self.data['variant'] = variant
        
        def connect( ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments' ) -> NSValue:
            _check_bound_to(args, NSTypes.Logic)
            for i, arg in enumerate(args.args):
                if not isinstance(arg,NSValue) or arg.type != NSTypes.Logic:
                    raise FunctionException('Invalid argument #%d'%(i+1,))
                args.bound.data['children'].append(arg)
                arg.data['parents'].append(args.bound)
            return NULL()
            
        @NSValue.make_trait(NSTraits.Op.Gt)
        class __trait__Gt:
            def gt(ctx: 'NSEContext', frame: 'NSEFrame', args: 'NSFunction.Arguments'):
                _check_args(args, NSTypes.Logic, (NSTypes.Logic,))
                other, = args.args
                args.bound.data['children'].append(other)
                other.data['parents'].append(args.bound)
                return NULL()
            
    @NSValue.make_class
    class Decorator:
        pass
    
    @NSValue.make_class
    class Component:
        def __init__( self: NSValue ):
            self.props['inputs'] = NSValue.Array([])
            self.props['outputs'] = NSValue.Array([])

NSValue._latetype()

NULL = lambda: NSValue(None,NSKind.Null,None)
TRUE = lambda: NSValue(True,NSTypes.Boolean,None)
FALSE = lambda: NSValue(False,NSTypes.Boolean,None)

class NSEVars:
    
    parent : Optional['NSEVars']
    vars   : dict
    locked : bool
    
    def __init__(self,v:Optional[Union['NSEVars',dict]]=None,locked:bool=False):
        self.locked = locked
        if not v:
            self.parent = None
            self.vars = {}
        elif type(v) == dict:
            self.parent = None
            self.vars = v
        elif type(v) == NSEVars:
            self.parent = v
            self.vars = {}
        else:
            raise TypeError(v)
        
    def extend(self,v:Optional[dict]=None) -> 'NSEVars':
        u = NSEVars(self)
        if v: 
            u.vars.update(v)
        return u
    
    def get(self,name:str) -> tuple[bool,Any]:
        if name in self.vars:
            return (True,self.vars[name])
        elif self.parent:
            return self.parent.get(name)
        return (False,None)
    
    def set(self,name:str,value:Any) -> bool:
        if name in self.vars:
            if self.locked:
                return False
            self.vars[name] = value
            return True
        elif self.parent:
            return self.parent.set(name,value)
        return False
    
    def new(self,name:str,value:Any):
        self.vars[name] = value
        
class NSEFrame:
    
    vars   : NSEVars
    parent : Optional['NSEFrame']
    
    def __init__( self, vars: NSEVars, parent: Optional['NSEFrame'] = None ):
        self.vars = vars
        self.parent = parent
        
    def __call__( self, vars: Optional[dict] = None ) -> 'NSEFrame':
        return NSEFrame(self.vars.extend(vars),self)

NSEExecutor = Callable[[ns.Node,NSEFrame,'NSEContext'],NSValue]
_executors : dict[Type[ns.Node],NSEExecutor] = {}

class NSEExecutors:
    
    executors : dict[Type[ns.Node],NSEExecutor] = {}
    
    E = TypeVar('E',bound=NSEExecutor)
    def _executor( t: Type[ns.Node] ) -> Callable[[E],E]:
        def __executor( fun ):
            _executors[t] = fun
            return fun
        return __executor
    
    @_executor(ns.NodeBlock)
    def Block( node: ns.NodeBlock, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        v = NULL()
        for node in node.children:
            v = ctx.exec(node,frame)
        return v
            
    @_executor(ns.NodeExpression)
    def Expression( node: ns.NodeExpression, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        if node.expression == None:
            return NULL()
        return ctx.exec(node.expression,frame)
    
    @_executor(ns.NodeName)
    def Name( node: ns.NodeName, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        found, value = frame.vars.get(node.name)
        if not found:
            raise NSEException.fromNode('No such variable exists in this scope',node)
        return value
    
    @_executor(ns.NodeLet)
    def Let( node: ns.NodeLet, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        value = ctx.exec(node.expr,frame) if node.expr != None else NULL()
        frame.vars.new(node.name,value)
        return value
                
    @_executor(ns.NodeCall)
    def Call( node: ns.NodeCall, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        value = ctx.exec(node.value,frame)
        kwargs = {} # TODO: Implement keyword arguments (could probably also do something about them in the parser)
        args = [ctx.exec(arg,frame) for arg in node.args]
        
        if value.type == NSTypes.Function:
            f = value.data['__function'].get('func',None) 
            if f and isinstance(f,NSFunction):    
                try:
                    return f.call(ctx,frame,NSFunction.Arguments(args,kwargs,value,value.data['__function'].get('bound',None)))
                except FunctionException as error:
                    raise NSEException.fromNode(error.message or '',node)
                
        if value.type == NSTypes.Decorator:
            if len(args) == 0:
                raise NSEException.fromNode('Inline decorator calls require at least one argument', node)
            if 'post' in value.data:
                f = value.data['post']
                f(ctx, frame, args[0], args[1:], node, ns.NodeDecorator(node.tokens, node.i, node))
            return args[0]
        
        raise NSEException.fromNode('%s is not callable'%('null' if value.type==NSKind.Null else 'Value',),node)
    
    @_executor(ns.NodeAccessDot)
    def AccessDot( node: ns.NodeAccessDot, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        value = None
        if node.node:
            value = ctx.exec(node.node, frame)
        else:
            found, value = frame.vars.get('self')
            if not found:
                raise NSEException.fromNode('Self does not exist in this scope',node)
        return value.get(node.prop)

    @_executor(ns.NodeAccessColon)
    def AccessColon( node: ns.NodeAccessColon, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        value = None
        if node.node:
            value = ctx.exec(node.node, frame)
        else:
            found, value = frame.vars.get('self')
            if not found:
                raise NSEException.fromNode('Self does not exist in this scope',node)
             
        val = value.get(node.prop,False,True) if value.type != NSTypes.Module else value.get(node.prop)
        if val.type == NSTypes.Function:
            val = NSValue({'__function':{'func':val.data['__function'].get('func',None),'bound':value}},val.type,val.props)
        return val
    
    @_executor(ns.NodeAccessColonDouble)
    def AccessColonDouble( node: ns.NodeAccessColonDouble, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        value = None
        if node.node:
            value = ctx.exec(node.node, frame)
        else:
            found, value = frame.vars.get('self')
            if not found:
                raise NSEException.fromNode('Self does not exist in this scope',node)
        val = value.get(node.prop,False,True) if value.type != NSTypes.Module else value.get(node.prop)
        return val

                
    @_executor(ns.NodeOperatorBinary)
    def OperatorBinary( node: ns.NodeOperatorBinary, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        op = node.op.t
        
        if op == '=':
            
            right = ctx.exec(node.right, frame)
            assign(node.left, right, frame, ctx)
            return right
            
        elif op == '==':
            
            left: NSValue = ctx.exec(node.left, frame)
            right: NSValue = ctx.exec(node.right, frame)
            
            if left.type in (NSKind.Class, NSKind.Trait, NSKind.Null, NSKind.Ref):
                return NSValue.Boolean(left == right)
            
            equals = left.get_trait_method(NSTraits.Op.Eq, 'eq')
            
            if not equals:
                return NSValue.Boolean(left == right)
            
            result = equals.call(ctx, frame, NSFunction.Arguments([right],{},equals,left))
            
            if result.type != NSTypes.Boolean:
                raise NSEException.fromNode('Non-boolean return value from trait Op.Eq', node)
            
            return result
        
        else:
            
            left = ctx.exec(node.left, frame)
            right = ctx.exec(node.right, frame)
            
            op_data = {
                '>' : ( NSTraits.Op.Gt, 'gt' ),
                '<' : ( NSTraits.Op.Lt, 'lt' ),
                '+' : ( NSTraits.Op.Add, 'add' ),
                '-' : ( NSTraits.Op.Sub, 'sub' ),
                '*' : ( NSTraits.Op.Mul, 'mul' ),
                '/' : ( NSTraits.Op.Div, 'div' ),
            }.get(op,None)
            
            if not op_data:
                raise NSEException.fromToken('Unimplemented operation \'%s\''%(op),node.op)
            
            if left.type:
                method = left.get_trait_method(op_data[0], op_data[1])
                if method:
                    try:
                        return method.call(ctx, frame,  NSFunction.Arguments([right],{},method,left))
                    except FunctionException as error:
                        raise NSEException.fromNode(error.message or '',node)
                raise NSEException.fromToken('Unsupported operation \'%s\' between `%s` and `%s`'%(op,toNSString(ctx,frame,left.type),toNSString(ctx,frame,right.type)),node.op)
            
            return NULL()
        
    @_executor(ns.NodeOperatorPostfix)
    def OperatorPostfix( node: ns.NodeOperatorPostfix, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        op = node.op.t
        
        value = ctx.exec(node.value, frame)
        
        op_data = {
            '++' : ( NSTraits.Op.Inc, 'inc' ),
            '--' : ( NSTraits.Op.Dec, 'dec' ),
        }.get(op,None)
        
        if not op_data:
            raise NSEException.fromToken('Unimplemented operation \'%s\''%(op),node.op)

        method = value.get_trait_method(op_data[0], op_data[1])
        if method:
            try:
                result = method.call(ctx, frame,  NSFunction.Arguments([],{},method,value))
                assign(node.value, result, frame, ctx)
                return value
            except FunctionException as error:
                raise NSEException.fromNode(error.message or '',node)
        raise NSEException.fromToken('Unsupported operation \'%s\' for `%s`'%(op,toNSString(ctx,frame,value.type)),node.op)
    
    @_executor(ns.NodeOperatorPrefix)
    def OperatorPrefix( node: ns.NodeOperatorPrefix, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        op = node.op.t
        
        if op == '&':

            return NSValue(ctx.exec(node.value, frame, False), NSKind.Ref)
        
        elif op == '*':
            
            value = ctx.exec(node.value, frame)
            
            if value.type == NSKind.Ref:
                return value.data
            
            raise NSEException.fromToken('Can\'t dereference `%s`'%(toNSString(ctx,frame,value.type),),node.op)
            
        else:
            
            value = ctx.exec(node.value, frame)
            
            op_data = {
                '++' : ( NSTraits.Op.Inc, 'inc' ),
                '--' : ( NSTraits.Op.Dec, 'dec' ),
            }.get(op,None)
            
            if not op_data:
                raise NSEException.fromToken('Unimplemented operation \'%s\''%(op),node.op)

            method = value.get_trait_method(op_data[0], op_data[1])
            if method:
                try:
                    result = method.call(ctx, frame,  NSFunction.Arguments([],{},method,value))
                    assign(node.value, result, frame, ctx)
                    return result
                except FunctionException as error:
                    raise NSEException.fromNode(error.message or '',node)
            raise NSEException.fromToken('Unsupported operation \'%s\' for `%s`'%(op,toNSString(ctx,frame,value.type)),node.op)
        
    @_executor(ns.NodeIf)
    def If( node: ns.NodeIf, frame: NSEFrame, ctx: 'NSEContext' ):
        value = ctx.exec(node.condition, frame)
        
        # TODO: Add truthiness trait?
        if value.type == NSKind.Null:
            res = False
        elif value.type == NSKind.Ref:
            res = value.data.type != NSKind.Null
        elif value.type == NSTypes.String:
            res = len(value.data) > 0
        elif value.type == NSTypes.Number:
            res = value.data != 0
        elif value.type == NSTypes.Boolean:
            res = value.data
        else:
            res = True
        
        node = node.expression if res else \
               node.otherwise
        
        return ctx.exec(node,frame) if node else NULL()

    @_executor(ns.NodeString)
    def String( node: ns.NodeString, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        return NSValue.String(node.value)

    @_executor(ns.NodeNumber)
    def Number( node: ns.NodeNumber, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        return NSValue.Number(node.value)

    @_executor(ns.NodeFunction)
    def Function( node: ns.NodeFunction, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        func = NSFunctionCode(node,frame)
        value = NSValue({'__function':{'func':func,'bound':None}},NSTypes.Function)
        if node.name:
            frame.vars.new(node.name,value)
        return value

    @_executor(ns.NodeArray)
    def Array( node: ns.NodeArray, frame: NSEFrame, ctx: 'NSEContext' ) -> NSValue:
        return NSValue.Array([ctx.exec(item,frame) for item in node.items])

    @_executor(ns.NodeReturn)
    def Return( node: ns.NodeReturn, frame: NSEFrame, ctx: 'NSEContext' ):
        raise RewindReturn(ctx.exec(node.value,frame) if node.value else NULL())
    
    @_executor(ns.NodeBreak)
    def Break( node: ns.NodeBreak, frame: NSEFrame, ctx: 'NSEContext' ):
        raise RewindBreak(ctx.exec(node.value,frame) if node.value else NULL())
    
    @_executor(ns.NodeContinue)
    def Continue( node: ns.NodeContinue, frame: NSEFrame, ctx: 'NSEContext' ):
        raise RewindContinue(ctx.exec(node.value,frame) if node.value else NULL())
                
    @_executor(ns.NodeFor)
    def For( node: ns.NodeFor, frame: NSEFrame, ctx: 'NSEContext' ):
        iterable = ctx.exec(node.iterable, frame)
        items = []
        if iterable.type == NSTypes.Array:
            items = iterable
        else:
            itemsFn = iterable.get_trait_method(NSTraits.Iterator,'items')
            if not itemsFn:
                raise NSEException.fromNode('Value is not iterable',node.iterable)
            items = itemsFn.call(ctx,frame,NSFunction.Arguments([],{},itemsFn,iterable))
        out = NULL()
        for i, item in enumerate(items.data['items']):
            v = {
                node.name_it.t: item
            }
            if node.name_i != None:
                v[node.name_i.t] = NSValue.Number(i)
            try:
                out = ctx.exec(node.body,frame(v))
            except RewindBreak as brk:
                return brk.value
            except RewindContinue as cnt:
                out = cnt.value
        return out
            
    @_executor(ns.NodeWhile)
    def While( node: ns.NodeWhile, frame: NSEFrame, ctx: 'NSEContext' ):
        v = NULL()
        
        while True:
            value = ctx.exec(node.condition, frame)
            
            # TODO: Add truthiness trait?
            if value.type == NSKind.Null:
                res = False
            elif value.type == NSKind.Ref:
                res = value.data.type != NSKind.Null
            elif value.type == NSTypes.String:
                res = len(value.data) > 0
            elif value.type == NSTypes.Number:
                res = value.data != 0
            elif value.type == NSTypes.Boolean:
                res = value.data
            else:
                res = True
                
            if not res:
                break
            
            if node.body:
                try:
                    v = ctx.exec(node.body, frame)
                except RewindBreak as brk:
                    return brk.value
                except RewindContinue as cnt:
                    v = cnt.value
            
        return v

    @_executor(ns.NodeRefExpression)
    def RefExpression( node: ns.NodeRefExpression, frame: NSEFrame, ctx: 'NSEContext' ):
        value = ctx.exec(node.value,frame,not node.ref)
        name = node.name.t if node.name != None else 'it'
        if node.ref:
            value = NSValue(value, NSKind.Ref)
        out = ctx.exec(node.expression,frame({name:value,'self':value}))
        return out if node.takeResult else value
    
    @_executor(ns.NodeImport)
    def NodeImport( node: ns.NodeImport, frame: NSEFrame, ctx: 'NSEContext' ):
        for name in node.names:
            paths = [
                pathHere.joinpath(name+'.ns').resolve()
            ]
            for p in paths:
                if p.exists():
                    # TODO: Maybe cache the imports?
                    source = ns.Source.fromFile(p)
                    tokens = ns.tokenize(source)
                    tree = ns.parse(tokens)
                    result = exec_code(tree)
                    frame.vars.new(name,NSValue(None,NSTypes.Module,result.frame.vars.vars))
                    break
        return NULL()
                    
NSEExecutors.executors = _executors
del _executors

def apply_decorators_pre(ctx: 'NSEContext', frame: NSEFrame, node: ns.DecoratableNode, env: dict[str,Any]):
    for dec in node.get_decorators():
        found, decorator = frame.vars.get(dec.name)
        if not found:
            raise NSEException.fromNode('No such variable exists in this scope',dec)
        for arg in dec.args:
            args.append(ctx.exec(arg.expression,frame))
        if decorator.type == NSTypes.Function:
            pass
        elif decorator.type == NSTypes.Decorator:
            # TODO: Add support for NS functions
            if 'pre' in decorator.data:
                f = decorator.data['pre']
                f(ctx,frame,args,node,dec)
        else:
            raise NSEException.fromNode('Value is not a decorator',node)        

def apply_decorators_post(ctx: 'NSEContext', frame: NSEFrame, node: ns.DecoratableNode, env: dict[str,Any], value: NSValue):
    for dec in node.get_decorators():
        found, decorator = frame.vars.get(dec.name)
        if not found:
            raise NSEException.fromNode('No such variable exists in this scope',dec)
        args = []
        for arg in dec.args:
            args.append(ctx.exec(arg.expression,frame))
        if decorator.type == NSTypes.Function:
            f = decorator.data['__function'].get('func',None)
            # if not f or not isinstance(f,NSFunction):
            #     raise NSEException.fromNode('Value is not callable',node)
            v = util.copy(ctx, frame, value)
            r = f.call(ctx,frame,NSFunction.Arguments([v,NSValue.Array(args)],{},decorator,decorator.data['__function'].get('bound',None)))     
            util.assign_ref(value,r)
        elif decorator.type == NSTypes.Decorator:
            # TODO: Add support for NS functions
            if 'post' in decorator.data:
                f = decorator.data['post']
                f(ctx,frame,value,args,node,dec)
        else:
            raise NSEException.fromNode('Value is not a decorator',node)

class NSEContext:    
    
    root_frame : NSEFrame
    # TODO: Add trace
        
    def __init__(self, root_frame: NSEFrame):
        self.root_frame = root_frame
    
    def exec(self, node: ns.Node, frame: NSEFrame, attempt_copy: bool = True) -> NSValue:
        e = NSEExecutors.executors.get(type(node))
        if not e:
            raise ValueError('Unsupported node type `%s`'%(type(node).__name__,))
        if isinstance(e,type):
            raise ValueError('Legacy node executor for `%s`'%(type(node).__name__))
        if e == NSEExecutors.Block:
            frame = frame()
        env = {
            'result': None,
            'copy': None,
        }
        if isinstance(node,ns.DecoratableNode):
            apply_decorators_pre(self, frame, node, env)
        env['result'] = e(node,frame,self)
        if isinstance(node,ns.DecoratableNode):
            apply_decorators_post(self, frame, node, env, env['result'])
        if not attempt_copy if env['copy'] == None else env['copy']:
            return env['result']
        return util.copy(self, frame, env['result'])
    
def toNSString(ctx: NSEContext, frame: NSEFrame, v:NSValue, h:bool=True, rep:bool=False) -> str:
    if v.type == NSKind.Null:
        return 'null'
    elif v.type == NSKind.Ref:
        return '&'+toNSString(ctx,frame,v.data,rep=True)
    elif v.type == NSKind.Class:
        cls = v.data.get('__class',{}).get('class',None)
        return '<class %s>'%(cls.__name__) if cls else repr(v)
    elif v.type == NSKind.Trait:
        return '<trait>'
    elif v.type == NSTypes.String:
        return repr(v.data) if rep else v.data
    elif v.type == NSTypes.Number:
        return str(int(v.data)) if int(v.data) == v.data else str(v.data)
    elif v.type == NSTypes.Boolean:
        return ('false','true')[v.data]
    elif v.type == NSTypes.Array:
        return '['+', '.join(toNSString(ctx,frame,v,rep=True) for v in v.data['items'])+']'
    elif h:
        toString = v.get_trait_method(NSTraits.ToString,'toString')
        if toString:
            r = toString.call(ctx,frame,NSFunction.Arguments([],{},toString,v))
            if isinstance(r,NSValue) and r.type == NSTypes.String:
                return toNSString(ctx, frame, r, False)
    cls = v.type.data.get('__class',{}).get('class',None)
    return '<%s @%s>'%(cls.__name__,hex(id(v))[2:]) if cls else repr(v)
    
@NSValue.Function
def ns_print(ctx: NSEContext, frame: NSEFrame, args: NSFunction.Arguments) -> NSValue:
    s = ''
    for i, v in enumerate(args.args):
        s += toNSString(ctx, frame, v, True)
        if i < len(args.args)-1:
            s += ' '
    print(s)
    return NULL()

GATE_AND  = 0
GATE_OR   = 1
GATE_XOR  = 2
GATE_NAND = 3
GATE_NOR  = 4
GATE_NXOR = 5
    
def gate_generator( variant ):
    @NSValue.Function
    def gate(ctx: NSEContext, frame: NSEFrame, args: NSFunction.Arguments) -> NSValue:
        return NSTypes.Logic.instantiate(variant)
    return gate
    
@NSValue.BasicDecorator
def export(ctx: NSEContext, frame: NSEFrame, value: NSValue, args: list[NSValue], node: ns.DecoratableNode, dec: ns.NodeDecorator):
    name = None
    if isinstance(node, ns.NodeFunction):
        name = node.name
    elif isinstance(node, ns.NodeLet):
        name = node.name
    if name:
        ctx.root_frame.vars.new(name, value)
    
@NSValue.Function
def require(ctx: NSEContext, frame: NSEFrame, args: NSFunction.Arguments) -> NSValue:
    _check_called_with(args, (NSTypes.String,))
    found, comp = exec_file(pathlib.Path(args.args[0].data).resolve()).frame.vars.get('component')
    if not found:
        raise FunctionException('Could not retreive component from required file')
    return comp
    
globals = NSEVars({
    'print': ns_print,
    'and': gate_generator(GATE_AND),
    'or': gate_generator(GATE_OR),
    'xor': gate_generator(GATE_XOR),
    'nand': gate_generator(GATE_NAND),
    'nor': gate_generator(GATE_NOR),
    'nxor': gate_generator(GATE_NXOR),
    'true': TRUE(),
    'false': FALSE(),
    'null': NULL(),
    'export': export,
    'require': require
},True)

class ExecutionResult:
    
    frame : NSEFrame
    
    def __init__(self, frame: NSEFrame):
        self.frame = frame

def exec_code( root: ns.NodeBlock, locals: dict = None ) -> ExecutionResult:

    root_frame = NSEFrame(globals.extend(locals or {}),None)

    context = NSEContext(root_frame)
    try:
        context.exec(root,root_frame)
    except RewindReturn as ret:
        if ret.value:
            if ret.value.type == NSTypes.Number:
                exit(int(ret.value.data))
        exit(0)
    except RewindBreak:
        print('Illegal break statement')
        exit(1)
    except RewindContinue:
        print('Illegal continue statement')
        exit(1)
    except NSEException as e:
        print(e)
        exit(1)

    return ExecutionResult(root_frame)

def exec_file( path: str ) -> Union[ExecutionResult,NSEException,ns.ParseError]:
    source = ns.Source.fromFile( path )
    tokens = ns.tokenize( source )
    tree   = ns.parse( tokens )
    if isinstance(tree, ns.ParseError):
        raise tree
    # TODO: re-implement this, somehow     
    # if consume_ns_arg('-ast'):
    #     print(explore(tree))
    #     exit(0)
    component = NSTypes.Component.instantiate()
    @NSValue.BasicDecorator
    def cp_input(ctx: NSEContext, frame: NSEFrame, value: NSValue, args: list[NSValue], node: ns.DecoratableNode, dec: ns.NodeDecorator):
        component.props['inputs'].data['items'].append(value)
    @NSValue.BasicDecorator
    def cp_output(ctx: NSEContext, frame: NSEFrame, value: NSValue, args: list[NSValue], node: ns.DecoratableNode, dec: ns.NodeDecorator):
        component.props['outputs'].data['items'].append(value)
    return exec_code(tree,{
        'component': component,
        'input': cp_input,
        'output': cp_output
    })

mainPath = pathlib.Path(args[0]).resolve()
result = exec_file(mainPath)
if isinstance(result, ns.ParseError):
    print(result)

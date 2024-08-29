from typing import Union, Any, Callable, Type, Optional, TypeVar, Generic, Iterable

import ns, sys

args = sys.argv[1:]

if len(args) == 0:
    print('Missing source file')
    exit(1)

source = ns.Source.fromFile(args[0])

tokens = ns.tokenize( source )
tree   = ns.parse( tokens )

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

if isinstance(tree,ns.ParseError):
    print(tree)
    exit(1)
    
if consume_ns_arg('-ast'):
    print(explore(tree))
    exit(0)
    
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
    
    def call( self, ctx: 'NSEContext', args: Arguments ):
        raise RuntimeError('That should not have happened')
    
class NSFunctionNative(NSFunction):
    
    callback : Callable[['NSEContext',NSFunction.Arguments],'NSValue']
    
    def __init__( self, callback: Callable[['NSEContext',NSFunction.Arguments],'NSValue'] ):
        super().__init__()
        self.callback = callback
        
    def call( self, ctx: 'NSEContext', args: NSFunction.Arguments ):
        ctx.push_value(NSValue.sanitize(self.callback(ctx,args)))
        
class NSFunctionCode(NSFunction):
    
    func  : ns.NodeFunction
    frame : 'NSEFrame'
    
    def __init__( self, func: ns.NodeFunction, frame: 'NSEFrame' ):
        super().__init__()
        self.func = func
        self.frame = frame
        
    def call( self, ctx: 'NSEContext', args: NSFunction.Arguments ):
        mapping = dict((param.name,None) for param in self.func.pararameters)
        # TODO: Handle default parameter values
        #       (+ change the scheme, as it requires execution of code :/)
        for name, arg in args.kwargs.items():
            if name in mapping:
                mapping[name] = arg
            else:
                raise NSEException.fromNode('Argument %s does not exist in this function'%(name,),ctx.top().node)
        for arg in args.args:
            found = False
            for name, val in mapping.items():
                if val == None:
                    mapping[name] = arg
                    found = True
                    break
            if not found:
                raise NSEException.fromNode('Unexpected extra argument',ctx.top().node)
        for name, val in mapping.items():
            if val == None:
                raise NSEException.fromNode('Missing value for argument %s'%(name,),ctx.top().node)
        frame = self.frame(mapping)
        frame.vars.new('self',args.bound or NULL)
        if self.func.body == None:
            ctx.push_value(NULL)
        else:
            ctx.eval(self.func.body,frame)
    
class Prop:
    
    class Const: pass
    
    value  : 'NSValue'
    getter : Optional['NSFunction']
    setter : Optional[Union['NSFunction',Const]]
    
    def __init__(self, value: 'NSValue', getter: Optional['NSFunction'] = None, setter: Optional[Union['NSFunction',Const]] = None):
        self.value  = value
        self.getter = getter
        self.setter = setter

class NSKind:
    
    class Class():pass
    
    class Trait():pass
    
    class Null():pass
    
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
        str: lambda v: NSValue.String(v),
        int:   lambda v: NSValue.Number(v),
        float: lambda v: NSValue.Number(v),
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
        
    def get( self, prop: str, searchInstance: Optional[bool] = True, searchClass: Optional[bool] = False ) -> Optional['NSValue']:
        if self.type == NSKind.Null:
            return None # TODO: THROW ERROR
        v = None
        if searchInstance:
            v = self.props.get(prop,None)
        if searchClass and v == None:
            v = self.type.props.get(prop,None)
        return v
    
    S = TypeVar('S',bound='NSValue')
    def set( self, prop: str, value: S ) -> S:
        if self.type in (NSKind.Null,NSKind.Class,NSKind.Trait):
            return None # TODO: THROW ERROR
        self.props[prop] = value
        return value
        
    @staticmethod
    def sanitize( value: Any ) -> 'NSValue':
        if value == None:
            return NULL
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
    def create_trait() -> 'NSValue':
        return NSValue({
            
        },NSKind.Trait)
        
    @staticmethod
    def make_trait( target ):
        class wrapper:
            def __init__( self, trait ):
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
        return NSValue._latevalue({'__boolean':bool(value)},'NSTypes.Boolean',None)
    
    @staticmethod
    def Array( items: list['NSValue'] ) -> 'NSValue':
        return NSValue._latevalue({'items':items},'NSTypes.Array')

class NSTraits:
    
    ToString = NSValue.create_trait()
    
    Iterator = NSValue.create_trait()

    class Op:
        
        Add = NSValue.create_trait()
        Sub = NSValue.create_trait()
        Mul = NSValue.create_trait()
        Div = NSValue.create_trait()
        
        Eq = NSValue.create_trait()
        Gt = NSValue.create_trait()
        Lt = NSValue.create_trait()

class NSTypes:

    @NSValue.make_class
    class Function:
        def bind(ctx: 'NSEContext', args: 'NSFunction.Arguments') -> NSValue:
            f = args.bound
            if not isinstance(f,NSValue) or f.type != NSTypes.Function:
                raise NSEException.fromNode('Unbound method call',ctx.top().node)
            if len(args.args) == 0:
                raise NSEException.fromNode('Missing bind target',ctx.top().node)
            b = args.args[0]
            return NSValue({'__function':{'func':f.data['__function'].get('func',None),'bound':b}},f.type,f.props|{'bound':b})

    @NSValue.make_class
    class String:
        @NSValue.make_trait(NSTraits.Op.Lt)
        class __trait__Lt:
            def lt(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.String:
                    return None
                return TRUE if args.bound.data<other.data else FALSE
            
        @NSValue.make_trait(NSTraits.Op.Gt)
        class __trait__Gt:
            def gt(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.String:
                    return None
                return TRUE if args.bound.data>other.data else FALSE
            
        @NSValue.make_trait(NSTraits.Op.Eq)
        class __trait__Eq:
            def eq(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.String:
                    return FALSE
                return TRUE if args.bound.data==other.data else FALSE

    @NSValue.make_class
    class Number:
        @NSValue.make_trait(NSTraits.Op.Lt)
        class __trait__Lt:
            def lt(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.Number:
                    return None
                return TRUE if args.bound.data<other.data else FALSE
            
        @NSValue.make_trait(NSTraits.Op.Gt)
        class __trait__Gt:
            def gt(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.Number:
                    return None
                return TRUE if args.bound.data>other.data else FALSE
            
        @NSValue.make_trait(NSTraits.Op.Add)
        class __trait__Add:
            def add(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.Number:
                    return None
                return NSValue.Number(args.bound.data+other.data)
            
        @NSValue.make_trait(NSTraits.Op.Eq)
        class __trait__Eq:
            def eq(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.Number:
                    return FALSE
                return TRUE if args.bound.data==other.data else FALSE
            
    @NSValue.make_class
    class Array:
        def __init__( self: NSValue ):
            pass
        
        def push( ctx: 'NSEContext', args: 'NSFunction.Arguments' ) -> NSValue:
            if not isinstance(args.bound,NSValue) or args.bound.type != NSTypes.Array:
                raise NSEException.fromNode('Unbound method call',ctx.top().node)
            args.bound.data['items'].append(args.args[0] if len(args.args) >= 1 else NULL)
            return NULL
        
        @NSValue.make_trait(NSTraits.Op.Add)
        class __trait__Add:
            def add(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.Array:
                    return None
                return NSValue.Array(args.bound.data['items']+other.data['items'])
                
    @NSValue.make_class
    class Boolean:
        pass
    
    @NSValue.make_class
    class And:
        def __init__( self: NSValue ):
            self.data['parents'] = []
            self.data['children'] = []
        
        def connect( ctx: 'NSEContext', args: 'NSFunction.Arguments' ) -> NSValue:
            if not isinstance(args.bound,NSValue) or args.bound.type != NSTypes.And:
                raise NSEException.fromNode('Unbound method call',ctx.top().node)
            for i, arg in enumerate(args.args):
                if not isinstance(arg,NSValue) or arg.type != NSTypes.And:
                    raise NSEException.fromNode('Invalid argument #%d'%(i+1,),ctx.top().node)
                args.bound.data['children'].append(arg)
                arg.data['parents'].append(args.bound)
            return NULL

        # @NSValue.make_trait(NSTraits.ToString)
        # class __trait__toString:
        #     def toString(ctx: 'NSEContext', args: 'NSFunction.Arguments') -> NSValue:
        #         return NSValue.String('[And Gate]')
            
        @NSValue.make_trait(NSTraits.Op.Gt)
        class __trait__Gt:
            def gt(ctx: 'NSEContext', args: 'NSFunction.Arguments'):
                other, = args.args
                if other.type != NSTypes.And:
                    raise NSEException.fromNode('Invalid connection target',ctx.top().node.right)
                args.bound.data['children'].append(other)
                other.data['parents'].append(args.bound)
                return NULL

NSValue._latetype()

NULL = NSValue(None,NSKind.Null,None)
TRUE = NSValue({'__boolean':True},NSTypes.Boolean,None)
FALSE = NSValue({'__boolean':False},NSTypes.Boolean,None)

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
    
class NSEExecutor:
    
    def __init__(self):
        raise RuntimeError('That should not have happened')
    
    def next( self, ctx: 'NSEContext' ):
        raise RuntimeError('That should not have happened')
    
_executors : dict[Type[ns.Node],Type[NSEExecutor]] = {}
class NSEExecutors:
    
    executors : dict[Type[ns.Node],Type[NSEExecutor]] = {}
    
    E = TypeVar('E',bound=Type[NSEExecutor])
    def _executor( t: Type[ns.Node] ) -> Callable[[E],E]:
        def __executor( cls ):
            _executors[t] = cls
            return cls
        return __executor
    
    @_executor(ns.NodeBlock)
    class Block(NSEExecutor):
    
        node : ns.NodeBlock
    
        i : int
        
        def __init__(self, node:ns.NodeBlock):
            self.node = node
            self.i = 0
            
        def next( self, ctx: 'NSEContext' ):
            v = ctx.pop_value_any()
            state = ctx.top()
            if self.i >= len(state.node.children):
                ctx.pop()
                if len(ctx.callstack):
                    ctx.push_value(v or NULL)
                return
            ctx.eval(state.node.children[self.i],state.frame)
            self.i += 1
            
    @_executor(ns.NodeExpression)
    class Expression(NSEExecutor):
        
        node : ns.NodeExpression
        
        def __init__(self, node:ns.NodeExpression):
            self.node = node
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            if len(state.stack):
                v = ctx.pop_value()
                ctx.pop()
                ctx.push_value(v)
                return
            ctx.eval(state.node.expression,state.frame)
            
    @_executor(ns.NodeName)
    class Name(NSEExecutor):
        
        node : ns.NodeName

        def __init__(self, node:ns.NodeName):
            self.node = node
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            found, var = state.frame.vars.get(state.node.name)
            if not found:
                raise NSEException.fromNode('No such variable exists in this scope',self.node)
            ctx.pop()
            ctx.push_value(var)
            
    @_executor(ns.NodeLet)
    class Let(NSEExecutor):
        
        node : ns.NodeLet
    
        value : bool
        
        def __init__(self,node:ns.NodeLet):
            self.node = node
            self.value = False
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            if self.value:
                val = ctx.pop_value()
                state.frame.vars.new(self.node.name,val)
                ctx.pop()
                ctx.push_value(val)
            else:
                if self.node.expr:
                    ctx.eval(self.node.expr,state.frame)
                self.value = True
            
    @_executor(ns.NodeCall)
    class Call(NSEExecutor):
        
        node : ns.NodeCall
        
        func   : NSFunction
        fn     : NSValue
        args   : list[NSValue]
        kwargs : dict[str,NSValue]
        i      : int
        k      : Union[str,None]
        c      : bool
        
        def __init__(self, node:ns.NodeName):
            self.node = node
            self.func = None
            self.args = []
            self.kwargs = {}
            self.i = 0
            self.k = None
            self.c = False
            
        def _process_arg(self,ctx):
            state = ctx.top()
            arg = state.pop_any()
            if arg:
                if self.k:
                    self.kwargs[self.k] = arg
                    self.k = None
                else:
                    self.args.append(arg)
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            if self.func == None:
                if len(state.stack):
                    v = state.pop()
                    f = v.data['__function'].get('func',None) if v.type == NSTypes.Function else v.get('',False,True)
                    if not f or not isinstance(f,NSFunction):
                        raise NSEException.fromNode('%s is not callable'%('null' if v.type==NSKind.Null else 'Value',),self.node)
                    self.func = f
                    self.fn = v
                else:
                    ctx.eval(state.node.value,state.frame)
                return
            if self.c:
                v = ctx.pop_value()
                ctx.pop()
                ctx.push_value(v)
                return
            if self.i >= len(state.node.args):
                self.c = True
                self._process_arg(ctx)
                self.func.call(ctx,NSFunction.Arguments(self.args,self.kwargs,self.fn,self.fn.data['__function'].get('bound',None)))
                return
            self._process_arg(ctx)
            ctx.eval(state.node.args[self.i],state.frame)
            self.i += 1
            
    @_executor(ns.NodeAccessDot)
    class AccessDot(NSEExecutor):
        
        node : ns.NodeAccessDot
        
        def __init__(self, node:ns.NodeAccessDot):
            self.node = node
            self.value = None
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            value = state.pop_any()
            if not value:
                if self.node.node == None:
                    found, v = state.frame.vars.get('self')
                    ctx.push_value(v if found else NULL)
                else:
                    ctx.eval(self.node.node,state.frame)
            else:
                ctx.pop()
                ctx.push_value(value.get(self.node.prop) or NULL)
                
    @_executor(ns.NodeAccessColon)
    class AccessColon(NSEExecutor):
        
        node : ns.NodeAccessColon
        
        def __init__(self, node:ns.NodeAccessColon):
            self.node = node
            self.value = None
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            value = state.pop_any()
            if not value:
                if self.node.node == None:
                    found, v = state.frame.vars.get('self')
                    ctx.push_value(v if found else NULL)
                else:
                    ctx.eval(self.node.node,state.frame)
            else:
                ctx.pop()
                val = value.get(self.node.prop,False,True) or NULL
                if val.type == NSTypes.Function:
                    val = NSValue({'__function':{'func':val.data['__function'].get('func',None),'bound':value}},val.type,val.props)
                ctx.push_value(val)
                
    @_executor(ns.NodeAccessColonDouble)
    class AccessColonDouble(NSEExecutor):
        
        node : ns.NodeAccessColonDouble
        
        def __init__(self, node:ns.NodeAccessColonDouble):
            self.node = node
            self.value = None
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            value = state.pop_any()
            if not value:
                if self.node.node == None:
                    found, v = state.frame.vars.get('self')
                    ctx.push_value(v if found else NULL)
                else:
                    ctx.eval(self.node.node,state.frame)
            else:
                ctx.pop()
                ctx.push_value(value.get(self.node.prop,False,True) or NULL)
                
    @_executor(ns.NodeOperatorBinary)
    class OperatorBinary(NSEExecutor):
        
        node : ns.NodeOperatorBinary
        
        left : NSValue
        
        def __init__(self, node:ns.NodeOperatorBinary):
            self.node = node
            self.left = None
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            value = state.pop_any()
            if not self.left:
                if value:
                    self.left = value
                    ctx.eval(self.node.right,state.frame)
                else:
                    ctx.eval(self.node.left,state.frame)
            else:
                left, right = self.left, value
                op = self.node.op.t
                
                if op == '=':
                    
                    if isinstance(self.node.left,ns.NodeName):  
                        state.frame.vars.set(self.node.left.name,right)
                        
                    else:
                        raise NSEException.fromNode('Unimplemented assign target \'%s\''%(type(self.node.left).__name__,),self.node.left)
                    
                    ctx.pop()
                    ctx.push_value(right)
                    
                else:
                    
                    op_data = {
                        '>' : ( NSTraits.Op.Gt, 'gt' ),
                        '<' : ( NSTraits.Op.Lt, 'lt' ),
                        '+' : ( NSTraits.Op.Add, 'add' ),
                        '-' : ( NSTraits.Op.Sub, 'sub' ),
                        '==' : ( NSTraits.Op.Eq, 'eq' )
                    }.get(op,None)
                    
                    result = NULL
                    if left.type:
                        method = left.get_trait_method(op_data[0],op_data[1])
                        if method:
                            method.call(ctx,NSFunction.Arguments([right],{},method,left))
                            result = ctx.pop_value_any()
                            # TODO: Add support for NS functions
                        elif op == '==':
                            result = TRUE if left == right else FALSE
                        else:
                            raise NSEException.fromToken('Unsupported operation \'%s\' between `%s` and `%s`'%(op,toNSString(ctx,right.type),toNSString(ctx,left.type)),self.node.op)
                    
                    ctx.pop()
                    ctx.push_value(result)
                    
    @_executor(ns.NodeIf)
    class If(NSEExecutor):
        
        node : ns.NodeIf
        value : NSValue
        ran : bool
        
        def __init__(self, node:ns.NodeIf):
            self.node = node
            self.value = None
            self.ran = False
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            v = state.pop_any()
            if not v:
                ctx.eval(self.node.condition,state.frame)
            else:
                if self.ran:
                    ctx.pop()
                    ctx.push_value(v or NULL)
                else:
                    self.ran = True
                    if v.type == NSKind.Null:
                        res = False
                    elif v.type == NSTypes.String:
                        res = len(v.data) > 0
                    elif v.type == NSTypes.Number:
                        res = v.data != 0
                    elif v.type == NSTypes.Boolean:
                        res = v.data['__boolean']
                    node = self.node.expression if res else \
                           self.node.otherwise
                    if node:
                        ctx.eval(node,state.frame)
                    
    @_executor(ns.NodeString)
    class String(NSEExecutor):
        
        node : ns.NodeString
        
        def __init__(self, node:ns.NodeString):
            self.node = node
            
        def next( self, ctx: 'NSEContext' ):
            ctx.pop()
            ctx.push_value(NSValue.String(self.node.value))
            
    @_executor(ns.NodeNumber)
    class Number(NSEExecutor):
        
        node : ns.NodeNumber
        
        def __init__(self, node:ns.NodeNumber):
            self.node = node
            
        def next( self, ctx: 'NSEContext' ):
            ctx.pop()
            ctx.push_value(NSValue.Number(self.node.value))
            
    @_executor(ns.NodeFunction)
    class Function(NSEExecutor):
        
        node : ns.NodeFunction
        
        def __init__(self, node:ns.NodeFunction):
            self.node = node
            
        def next( self, ctx: 'NSEContext' ):
            ctx.pop()
            frame = ctx.top().frame
            func = NSFunctionCode(self.node,frame)
            value = NSValue({'__function':{'func':func,'bound':None}},NSTypes.Function)
            ctx.push_value(value)
            if self.node.name:
                frame.vars.new(self.node.name,value)
                
    @_executor(ns.NodeReturn)
    class Return(NSEExecutor):
        
        node : ns.NodeReturn
        
        def __init__(self, node:ns.NodeReturn):
            self.node = node
            
        def next( self, ctx: 'NSEContext' ):
            retval = ctx.pop_value_any() if self.node.value else NULL
            if not retval:
                ctx.eval(self.node.value,ctx.top().frame)
            else:
                ctx.pop()
                state = None
                for _ in range(500):
                    s = ctx.pop()
                    if isinstance(s.node,ns.parser.NodeCall):
                        state = s
                        break
                if not state:
                    raise NSEException.fromNode('Failed to trace parent function call',self.node)
                ctx.pop()
                ctx.push_value(retval)
                
    @_executor(ns.NodeArray)
    class Array(NSEExecutor):
        
        node : ns.NodeArray
        
        items : list[NSValue]
        
        def __init__( self, node: ns.NodeArray ):
            self.node = node
            self.items = []
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            v = state.pop_any()
            if v != None:
                self.items.append(v)
            if len(self.items) >= len(self.node.items):
                ctx.pop()
                ctx.push_value(NSValue.Array(self.items))
            else:
                ctx.eval(self.node.items[len(self.items)],state.frame)
                
    @_executor(ns.NodeFor)
    class For(NSEExecutor):
        
        node : ns.NodeFor
        
        iterable : NSValue
        items : NSValue
        i : int
        
        def __init__( self, node: ns.NodeFor ) -> None:
            self.node = node
            self.iterable = None
            self.i = 0
            
        def next( self, ctx: 'NSEContext' ):
            state = ctx.top()
            if self.iterable == None:
                v = state.pop_any()
                if v != None:
                    self.iterable = v
                    if self.iterable.type == NSTypes.Array:
                        self.items = self.iterable
                    else:
                        itemsFn = self.iterable.get_trait_method(NSTraits.Iterator,'items')
                        if not itemsFn:
                            raise NSEException.fromNode('Value is not iterable',self.node.iterable)
                        itemsFn.call(ctx,NSFunction.Arguments([],{},itemsFn,self.iterable))
                else:
                    ctx.eval(self.node.iterable,state.frame)
            elif self.items == None:
                self.items = state.pop()
            else:
                if self.i >= len(self.items.data['items']):
                    ctx.pop()
                else:
                    v = {
                        self.node.name_it.t: self.items.data['items'][self.i]
                    }
                    if self.node.name_i != None:
                        v[self.node.name_i.t] = NSValue.Number(self.i)
                    ctx.eval(self.node.body,state.frame(v))
                    self.i += 1
                    
    @_executor(ns.NodeRefExpression)
    class RefExpression(NSEExecutor):
        
        node : ns.NodeRefExpression
        
        value : NSValue
        
        def __init__( self, node: ns.NodeRefExpression ):
            self.node = node
            self.value = None
            
        def next(self, ctx: 'NSEContext'):
            state = ctx.top()
            if not self.value:
                v = state.pop_any()
                if v != None:
                    self.value = v
                else:
                    ctx.eval(self.node.value,state.frame)
            else:
                v = state.pop_any()
                if v != None:
                    ctx.pop()
                    # ctx.push_value(v if self.node.ref else self.value)
                    ctx.push_value(self.value if self.node.ref else v)
                else:
                    name = self.node.name.t if self.node.name != None else 'it'
                    ctx.eval(self.node.expression,state.frame({name:self.value,'self':self.value}))
                    
NSEExecutors.executors = _executors
del _executors
        
class NSEContext:
    
    class State:
        
        frame : NSEFrame
        node  : ns.Node
        stack : list[NSValue]
        exec  : NSEExecutor
        
        def __init__(self, frame: NSEFrame, node: ns.Node, stack: Union[list[NSValue],None], executor: NSEExecutor):
            self.frame = frame
            self.node = node
            self.stack = stack or []
            self.exec = executor
            
        def push(self, value: NSValue):
            self.stack.append(value)
            
        def pop(self) -> NSValue:
            return self.stack.pop()
        
        def pop_any(self) -> Optional[NSValue]:
            return self.stack.pop() if len(self.stack) else None
        
    callstack : list[State]
    
    def __init__(self):
        self.callstack = []
        
    def eval(self, node: ns.Node, frame: NSEFrame):
        e = NSEExecutors.executors.get(type(node))
        if not e:
            raise ValueError('Unsupported node type `%s`'%(type(node).__name__,))
        if e == NSEExecutors.Block:
            frame = frame()
        self.callstack.append(NSEContext.State(frame,node,[],e(node)))
        return self
        
    def top(self) -> State:
        return self.callstack[-1]
    
    def pop(self) -> State:
        return self.callstack.pop()
    
    def push(self, state: State):
        self.callstack.append(state)
        return self
        
    def top_value(self) -> NSValue:
        return self.callstack[-1].stack[-1]
        
    def pop_value(self) -> NSValue:
        return self.callstack[-1].stack.pop()
    
    def pop_value_any(self) -> Optional[NSValue]:
        return self.callstack[-1].stack.pop() if len(self.callstack[-1].stack) else None
    
    def push_value(self, value: NSValue):
        self.callstack[-1].stack.append(value)
        return self
    
def toNSString(ctx: NSEContext, v:NSValue, h:bool=True, rep:bool=False) -> str:
    if v.type == NSKind.Null:
        return 'null'
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
        return ('false','true')[v.data['__boolean']]
    elif v.type == NSTypes.Array:
        return '['+', '.join(toNSString(ctx,v,rep=True) for v in v.data['items'])+']'
    elif h:
        toString = v.get_trait_method(NSTraits.ToString,'toString')
        if toString:
            toString.call(ctx,NSFunction.Arguments([],{},toString,v))
            r = ctx.pop_value_any()
            if isinstance(r,NSValue) and r.type == NSTypes.String:
                return toNSString(ctx, r, False)
    cls = v.type.data.get('__class',{}).get('class',None)
    return '<%s @%s>'%(cls.__name__,hex(id(v))[2:]) if cls else repr(v)
    
@NSValue.Function
def ns_print(ctx: NSEContext, args: NSFunction.Arguments) -> NSValue:
    s = ''
    for i, v in enumerate(args.args):
        s += toNSString(ctx, v, True)
        if i < len(args.args)-1:
            s += ' '
    print(s)
    return NULL
    
@NSValue.Function
def ns_and(ctx: NSEContext, args: NSFunction.Arguments) -> NSValue:
    return NSTypes.And.instantiate()
    
globals = NSEVars({
    'print': ns_print,
    'and': ns_and,
    'true': TRUE,
    'false': FALSE,
    'null': NULL,
},True)

root_frame = NSEFrame(globals.extend(),None)

context = NSEContext()
context.push(NSEContext.State(root_frame,tree,[],NSEExecutors.Block(tree)))

try:
    while len(context.callstack):
        top = context.top()
        # print(type(top.node).__name__,hex(id(top.node)),top.node.tokens.tokens[top.node.i])
        res = top.exec.next(context)
        if isinstance(res,NSEException):
            print(res)
            break
except NSEException as e:
    print(e)

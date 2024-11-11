from typing import Any, Union, Literal

class Source:
    """
    Used to store data from the source of a program
    """
    
    name : str
    body : str
    
    def __init__( self, name:str, body:str ):
        self.name = name
        self.body = body
        
    def lines( self ) -> list[str]:
        return list(map(lambda l:l.removesuffix('\r'),self.body.split('\n')))
        
    @staticmethod
    def fromFile( path:str ) -> 'Source':
        """
        Creates a new source from a file
        """
        body = ''
        with open(path,'rt') as file:
            body = file.read().replace('\r\n','\n')
        return Source(path,body)
    
class TokenEOF(str):
    """
    Used as the text of the token appended at the end of `tokenize`
    """
    
    def __init__(self):pass
    def __str__(self):return'<EOF>'
    def __repr__(self):return'<EOF>'
    pass
    
class Token:
    """
    Represents a single token
    """
    
    t : str
    c : int
    l : int
    i : int
    s : Source
    tags : list[tuple['Node',Union[str,None]]]
    
    def __init__( self, t:str, c:int, l:int, i:int, s:Source ):
        self.t = t
        self.c = c
        self.l = l
        self.i = i
        self.s = s
        self.tags = []
        
    def tag( self, node: 'Node', tag: str = None ):
        self.tags.append((node,tag))
    
    def isidentifier( self ) -> bool:
        return len(self.t) > 0 and self.t[0].lower() in 'abcdefghijklmnopqrstuvwxyz_$'
    
    def isnumeric( self ) -> bool:
        return self.t.isnumeric()
    
    def isstring( self ) -> bool:
        return self.t.startswith('"') and self.t.endswith('"')
    
    def __str__( self ) -> str:
        return 'Token<\x1b[33m%s\x1b[39m \x1b[35m%d\x1b[39m:\x1b[35m%d\x1b[39m>'%(self.t,self.l+1,self.c+1)

class Tokens:
    """
    Represents a group of tokens issued from the same source
    """
    
    source : Source
    tokens : list[Token]
    
    def __init__( self, source:Source ):
        self.source = source
        self.tokens = []
        
    def splitToken( self, token:Token ):
        assert token in self.tokens, 'token must be part of Tokens\' tokens'
        i = self.tokens.index(token)
        self.tokens.pop(i)
        c = token.c
        for j, t in reversed(tuple(enumerate(token.t))):
            self.tokens.insert(i,Token(t,c+j,token.l,token.i+j,token.s))
        
    def __str__(self) -> str:
        return 'Tokens['+', '.join(map(str,self.tokens))+']'
        
compoundTokens = [
    '...',
    '>>=',
    '<<=',
    '&&=',
    '||=',
    '==',
    '>=',
    '<=',
    '!=',
    '&&',
    '||',
    '>>',
    '<<',
    '+=',
    '-=',
    '*=',
    '/=',
    '%=',
    '^=',
    '&=',
    '|=',
    '++',
    '--',
    '<>',
    '<{',
    '}>',
    '->',
    '=>',
    '::',
    '//',
    '/*',
    '*/',
]

operators: list[dict[str,Union[Literal['prefix'],Literal['binary'],Literal['postfix']]]] = [
    {
        '++' : 'postfix',
        '--' : 'postfix',
        '*'  : 'postfix',
    },
    {
        '++' : 'prefix',
        '--' : 'prefix',
        '&'  : 'prefix',
        '*'  : 'prefix',
        '+'  : 'prefix',
        '-'  : 'prefix',
        '!'  : 'prefix',
        '~'  : 'prefix',
    },
    {
        '*' : 'binary',
        '/' : 'binary',
        '%' : 'binary',
    },
    {
        '+' : 'binary',
        '-' : 'binary',
    },
    {
        '>>' : 'binary',
        '<<' : 'binary',
    },
    {
        '==' : 'binary',
        '!=' : 'binary',
    },
    {
        '>'  : 'binary',
        '>=' : 'binary',
        '<=' : 'binary',
        '<'  : 'binary',
    },
    {
        '&' : 'binary',
    },
    {
        '^' : 'binary',
    },
    {
        '|' : 'binary',
    },
    {
        '&&' : 'binary',
    },
    {
        '||' : 'binary',
    },
    {
        '='   : 'binary',
        '+='  : 'binary', 
        '-='  : 'binary', 
        '*='  : 'binary', 
        '/='  : 'binary', 
        '%='  : 'binary', 
        '^='  : 'binary', 
        '&='  : 'binary', 
        '|='  : 'binary', 
        '&&=' : 'binary', 
        '||=' : 'binary', 
        '>>=' : 'binary', 
        '<<=' : 'binary', 
    },
    {
        '...' : 'prefix',
    },
]

operatorTokens: list[str] = [t for p in operators for t in p.keys()]

def tokenize(source: Source) -> Tokens:
    """
    Retrieves tokens from the provided source
    """
    
    tokens = Tokens(source)
    
    in_line_comment = False
    in_block_comment = False
    
    l,c = 0,0
    
    flags: dict[str,dict[str,Any]] = {}
    
    tmp = ''
    
    def sep(i,dooff=True):
        nonlocal tmp
        if in_line_comment or in_block_comment:
            return
        if len(tmp):
            tokens.tokens.append(Token(tmp,c-(dooff*len(tmp)),l,i,source))
            tmp = ''
    
    skip = 0
    for i,ch in enumerate(source.body):
        if skip > 0: 
            c += 1
            skip -= 1
            continue
        if 'str' in flags:
            s = flags.get('str')
            esc: dict = s.get('esc')
            if esc:
                def end(c:str):
                    nonlocal tmp
                    del s['esc']
                    tmp += c
                if not esc.get('n',False):
                    esc['n'] = True
                    if ch.lower() in 'xou':
                        esc['radix'] = ch.lower()
                    elif ch == 'n': end('\n')
                    elif ch == 'r': end('\r')
                    elif ch == 't': end('\t')
                    elif ch == '@': end('\0')
                    elif ch == '0': end('\0')
                    elif ch == 'e': end('\x1b')
                    elif ch == '^': end('\x1b')
                    else          : end(ch)
                    esc['v'] = ''
                else:
                    esc['v'] += ch
                    radix = esc.get('radix',None)
                    if radix:
                        if radix == 'x' and len(esc['v']) == 2:
                            end(chr(int(esc['v'],base=16)))
                        elif radix == 'o' and len(esc['v']) == 3:
                            end(chr(int(esc['v'],base=8)))
                        elif radix == 'u' and len(esc['v']) == 4:
                            end(chr(int(esc['v'],base=16)))
                    else:
                        raise RuntimeError('That should not happen, right ?')
            else:
                if ch == s.get('opens'):
                    tokens.tokens.append(Token('"'+tmp+'"',s.get('c'),s.get('l'),s.get('i'),source))
                    tmp = ''
                    del flags['str']
                elif ch == '\\':
                    s['esc'] = {'n':0,'v':''}
                else:
                    tmp += ch
        else:
            compound = False
            for t in compoundTokens:
                if source.body[i:i+len(t)] == t:
                    if t == '*/':
                        in_block_comment = False
                        tmp = ''
                        compound = True
                        skip = 1
                    elif in_block_comment or in_line_comment:
                        pass
                    elif t == '/*':
                        in_block_comment = True
                    elif t == '//':
                        in_line_comment = True
                    else:
                        sep(i)
                        tmp = t
                        sep(i,False)
                        skip = len(t)-1
                        compound = True
                    break
            if not compound and not (in_block_comment or in_line_comment):
                if ch in ' \t\n':
                    sep(i)
                elif ch in '.,:;/+-*=!?()[]{}<>@#~^&\\|':
                    sep(i)
                    tmp = ch
                    sep(i,False)
                elif ch in '`\'"':
                    flags['str'] = {'opens':ch,'c':c,'l':l,'i':i}
                else:
                    tmp += ch
        c += 1
        if ch == '\n':
            if in_line_comment:
                in_line_comment = False
                tmp = ''
            l += 1
            c = 0
    
    sep(len(source.body))
    
    tokens.tokens.append(Token(TokenEOF(),c,l,i,source))
    
    return tokens

class Enclosure:
    """
    Represents a currently opened block, delimited by the opening token and the expected closing character
    """
    
    start : Token
    end   : str
    
    def __init__( self, start:Token, end:str ):
        self.start = start
        self.end   = end

class ParseContext:
    """
    Holds the state of the parser
    """
    
    tokens  : Tokens
    ptr     : int
    node    : 'Node'
    enclose : list[Enclosure]
    
    def __init__( self, tokens:Tokens, node:'Node', ptr:int=0 ):
        self.tokens = tokens
        self.node = node
        self.ptr = ptr
        self.enclose = []
        
    def open( self, start:Token, end:str ):
        self.enclose.append(Enclosure(start,end))
        
    def close( self, token:Token ):
        if len(self.enclose) and self.enclose[-1].end == token.t:
            self.enclose.pop()
        else:
            raise ParseError.fromToken('Missmatched `%s`'%(token.t,), token)

class ParseError(BaseException):
    """
    Holds data about a parser (syntax) error
    """
    
    message : str
    l       : int
    c       : int
    s       : int
    source  : Source
    trace   : list[Any]
    
    def __init__( self, message:str, l:int, c:int, s:int, source:str ):
        self.message = message
        self.l = l
        self.c = c
        self.s = s
        self.source = source
        self.trace = []
        
    def __str__( self ) -> str:
        rline = self.source.lines()[self.l]
        line = rline.lstrip()     # removes all indent
        dl = len(rline)-len(line) # computes the shift caused by the indent
        msg = '\x1b[31;1mSyntax error\x1b[22;39m (\x1b[36m%s:%d:%d\x1b[39m):\n' % ( self.source.name, self.l+1, self.c+1 )
        msg += '  %s\n\n'  % ( self.message.replace('\n','\n  '), )
        msg += '  %s\n' %( line[:self.c-dl]+'\x1b[33m'+line[self.c-dl:self.c-dl+self.s]+'\x1b[39m'+line[self.c-dl+self.s:], )
        msg += '  %s' % ( ' '*(self.c-dl)+'^'+'~'*(self.s-1), )
        if len(self.trace):
            msg += '\n'
            for t in reversed(self.trace):
                if isinstance(t, Node):
                    msg += '\n\x1b[90min %s (%s:%d:%d)\x1b[39m' % ( type(t).__name__.removeprefix('Node'), t.tokens.source.name, t.tokens.tokens[t.i].l+1, t.tokens.tokens[t.i].c+1 )
                else:
                    msg += '\n\x1b[90min <%s>' % ( type(t).__name__ )
        return msg
    
    @staticmethod
    def fromToken( msg:str, tk:Token ) -> 'ParseError':
        return ParseError(msg, tk.l, tk.c, len(tk.t), tk.s)
        
class Node:
    """
    Represents an abstract node in an AST (should not be used directly)
    """
    
    tokens   : Tokens
    i        : int
    parent   : 'Node'
    
    def __init__( self, tokens:Tokens, i:int, parent:'Node' ):
        self.tokens = tokens
        self.i = i
        self.parent = parent
        
    def feed( self, token:Token, _ctx:ParseContext ) -> Union[ParseError,None]:
        """
        Called whenever the parser is processing a token inside of a node
        """
        return ParseError.fromToken('Something went very wrong right before here :/ Can\'t tell much more', token)

class DecoratableNode( Node ):
    decorators : list['NodeDecorator']
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.__decorators = []
        
    def add_decorators( self, *decorators: list['NodeDecorator'] ):
        self.__decorators.extend(decorators)
        
    def get_decorators( self ) -> list['NodeDecorator']:
        return self.__decorators

class NodeName( Node ):
    """
    Reference to a variable
    """
    
    name : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, name:str ):
        super().__init__(tokens,i,parent)
        self.name = name

class NodeNumber( Node ):
    """
    Number literal
    """
    
    value : Union[int,float]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, value:Union[int,float,str] ):
        super().__init__(tokens,i,parent)
        self.value = float(value) if type(value) == str else value
        
class NodeString( Node ):
    """
    String literal
    """
    
    value : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, value:str ):
        super().__init__(tokens,i,parent)
        self.value = value

class NodeAccessDot( Node ):
    """
    `.` accessor
    """
    
    node : Node
    prop : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, node:Node, prop:str ):
        super().__init__(tokens,i,parent)
        self.node = node
        self.prop = prop
        
class NodeAccessColon( Node ):
    """
    `:` accessor
    """
    
    node : Node
    prop : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, node:Node, prop:str ):
        super().__init__(tokens,i,parent)
        self.node = node
        self.prop = prop
        
class NodeAccessColonDouble( Node ):
    """
    `::` accessor
    """
    
    node : Node
    prop : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, node:Node, prop:str ):
        super().__init__(tokens,i,parent)
        self.node = node
        self.prop = prop
        
class NodeIndex( Node ):
    """
    `[...]` (index) operator
    """
    
    value : Node
    index : list['NodeExpression']
    sep   : Union[None,str]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, value:Node ):
        super().__init__(tokens,i,parent)
        self.value = value
        self.index = []
        self.idx = None
        self.sep = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if token.t == ']':
            token.tag(self,'close')
            if self.idx:
                self.index.append(self.idx)
            ctx.close(token)
            ctx.node = self.parent
        elif token.t in (',',':'):
            token.tag(self)
            self.sep = self.sep or token.t
            self.index.append(self.idx or NodeExpression(self.tokens,self.i,self,(*((self.sep,) if self.sep != None else (',',':')),']'),handleParent=True,allowEmpty=True))
            self.idx = None
        else:
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,(*((self.sep,) if self.sep != None else (',',':')),']'),handleParent=True,allowEmpty=True)
            self.idx = ctx.node
            ctx.ptr -= 1
        
class NodeCall( Node ):
    """
    `()` (call) operator
    """
    
    value : Node                   # the called value
    args  : list['NodeExpression'] # the arguments to the call
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, value:Node ):
        super().__init__(tokens,i,parent)
        self.value = value
        self.args = []
        self.arg = None

    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if token.t == ')':
            token.tag(self,'close')
            # Adds the last argument to the arguments list (if any)
            if self.arg:
                self.args.append(self.arg)
            # Ensures that no bracket was opened in the arguments and left unclosed
            ctx.close(token)
            ctx.node = self.parent
        # Adds the previous argument to the argument list, allowing empty arguments
        elif token.t == ',':
            token.tag(self)
            self.args.append(self.arg or NodeExpression(self.tokens,self.i,self,(',',')'),handleParent=True,allowEmpty=True))
            self.arg = None
        # Creates a new argument
        else:
            ctx.node = NodeExpression(self.tokens,self.i,self,(',',')'),handleParent=True,allowEmpty=True)
            self.arg = ctx.node
            # Makes sure that the expression also catches the first token
            ctx.ptr -= 1

class NodeOperatorPrefix( Node ):
    """
    Prefix operator
    """
    
    op    : Token
    value : 'NodeExpression'
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, op:Token, value:'NodeExpression' ):
        super().__init__(tokens,i,parent)
        self.op = op
        self.value = value
    
class NodeOperatorPostfix( Node ):
    """
    Postfix / Suffix operator
    """
    
    op    : Token
    value : 'NodeExpression'
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, op:Token, value:'NodeExpression' ):
        super().__init__(tokens,i,parent)
        self.op = op
        self.value = value

class NodeOperatorBinary( Node ):
    """
    Binary operator
    """
    
    op    : Token
    left  : 'NodeExpression'
    right : 'NodeExpression'
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, op:Token, right:'NodeExpression', left:'NodeExpression' ):
        super().__init__(tokens,i,parent)
        self.op = op
        self.left = left
        self.right = right
        
class NodeCast( Node ):
    """
    `... <> ...` (type cast) operator
    """
    
    value : 'NodeExpression'
    type  : 'NodeExpression'
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, value:'NodeExpression', cast:'NodeExpression' ):
        super().__init__(tokens,i,parent)
        self.value = value
        self.type = cast

class NodeExpression ( Node ):
    """
    An expression
    """
    
    expression : Union[Node,None]
    type       : bool
    
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, closeToken:tuple[str], handleParent:bool=False, allowEmpty:bool=False, finishEnclose:Union[str,None]=None, isType:bool=False ):
        """
        :param str closeToken: A string or list of string that should be used to close the expression
        :param bool handleParent: Whether the parsing should resume after (False) or at (True) the enclosing token
        :param bool allowEmpty: Whether the expression is allowed to be empty
        :param Union[str,None] finishEnclose: In the case of an expression that has a matching bracket, specifies the expected closing token
        """
        super().__init__(tokens,i,parent)
        self.closeToken = closeToken
        self.handleParent = handleParent
        self.allowEmpty = allowEmpty
        self.finishEnclose = finishEnclose
        self.type = isType
        self.n = 0
        self.buffer = []
        self.expression = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        # Checks if the current token is a closing token for the expression
        if token.t == self.closeToken if type(self.closeToken) == str else token.t in self.closeToken:
            # Checks for unfinished accessor operators
            if len(self.buffer) > 0 and type(self.buffer[-1]) == Token and self.buffer[-1].t in ('.',':'):
                return ParseError.fromToken('Unexpected end of expression after `%s`'%(self.buffer[-1].t,), token)
            # Checks for empty expression
            if not self.allowEmpty and len(self.buffer) == 0:
                return ParseError.fromToken('Unexpected empty expression', token)
            # Checks for surrounding brackets
            if self.finishEnclose:
                ctx.close(token)
            # 'Resolves' operators
            for prec in operators:
                ops = list(prec.keys())
                i = 0
                while i < len(self.buffer):
                    v = self.buffer[i]
                    if type(v) == Token and v.t in ops:
                        kind = prec.get(v.t)
                        if kind == 'prefix':
                            if ((i == 0 or type(self.buffer[i-1]) == Token) and i < len(self.buffer)-1) and type(self.buffer[i+1]) != Token:
                                op = self.buffer.pop(i)
                                value = self.buffer.pop(i)
                                n = NodeOperatorPrefix(self.tokens,self.tokens.tokens.index(v),self,op,value)
                                v.tag(n)
                                self.buffer.insert(i,n)
                                i = -1
                        elif kind == 'binary':
                            if i < len(self.buffer)-1 and i > 0 and type(self.buffer[i-1]) != Token and type(self.buffer[i+1]) != Token:
                                right = self.buffer.pop(i-1)
                                op = self.buffer.pop(i-1)
                                left = self.buffer.pop(i-1)
                                n = NodeOperatorBinary(self.tokens,self.tokens.tokens.index(v),self,op,left,right)
                                v.tag(n)
                                self.buffer.insert(i-1,n)
                                i = -1
                        elif kind == 'postfix':
                            if ((i == len(self.buffer)-1 or type(self.buffer[i+1]) == Token) and i > 0) and type(self.buffer[i-1]) != Token:
                                value = self.buffer.pop(i-1)
                                op = self.buffer.pop(i-1)
                                n = NodeOperatorPostfix(self.tokens,self.tokens.tokens.index(v),self,op,value)
                                v.tag(n)
                                self.buffer.insert(i-1,n)
                                i = -1
                        else:
                            return ParseError.fromToken('Invalid operation', v)
                    i += 1
            # Errors out if there are extra operators
            for v in self.buffer:
                if type(v) == Token:
                    return ParseError.fromToken('Unexpected token', v)
            # Errors out if there are multiple expressions inside of a single one
            if len(self.buffer) > 1:
                # TODO: Make a better guess for the location, lol
                msg = 'Malformed expression, perhaps you forgot %s %s%s%s?'%('a' if len(self.closeToken) == 1 else 'either',', '.join('\'%s\''%(tk,) for tk in self.closeToken[:-1]),' or ' if len(self.closeToken) > 1 else '',"'"+self.closeToken[-1]+"'")
                if isinstance(self.buffer[1], Token):
                    return ParseError.fromToken(msg, self.buffer[1])
                elif isinstance(self.buffer[1], Node):
                    return ParseError.fromToken(msg, self.buffer[1].tokens.tokens[self.buffer[1].i])
                else:
                    return ParseError.fromToken(msg, token)
            # Moves the pointer back in case of a handling parent so that it will also receive the closing token
            if self.handleParent:
                ctx.ptr -= 1
            self.expression = self.buffer[0] if len(self.buffer) else None
            ctx.node = self.parent
        # Dot and colon accessor operators
        elif len(self.buffer) > 0 and type(self.buffer[-1]) == Token and self.buffer[-1].t in ('.',':','::'):
            a = self.buffer.pop()
            if not token.isidentifier():
                return ParseError.fromToken('Expected identifier after `%s`'%(a.t,), token)
            v = None if len(self.buffer) == 0 else self.buffer.pop()
            cls = {
                '.' :  NodeAccessDot,
                ':' :  NodeAccessColon,
                '::' : NodeAccessColonDouble
            }[a.t]
            n = cls(self.tokens,self.tokens.tokens.index(a),self,v,token.t)
            token.tag(n)
            self.buffer.append(n)
        # Dot and colon accessor operators
        elif token.t in ('.',':','::'):
            if len(self.buffer) > 0 and type(self.buffer[-1]) == Token :
                return ParseError.fromToken('Unexpected token', token)
            else:
                self.buffer.append(token)
        elif token.t == '(':
            # Call operator
            if len(self.buffer) and not isinstance(self.buffer[-1],Token):
                value = self.buffer.pop()
                ctx.node = NodeCall(self.tokens,ctx.ptr,self,value)
                token.tag(ctx.node)
                self.buffer.append(ctx.node)
                ctx.open(token,')')
            # New expression
            else:
                ctx.node = NodeExpression(self.tokens,ctx.ptr,self,')',allowEmpty=True,finishEnclose=')')
                token.tag(ctx.node)
                self.buffer.append(ctx.node)
                ctx.open(token,')')
        elif token.t == '[':
            # Indexing operator
            # TODO: Move the common parts out of the if?
            if len(self.buffer) and not isinstance(self.buffer[-1],Token):
                value = self.buffer.pop()
                ctx.node = NodeIndex(self.tokens,ctx.ptr,self,value)
                token.tag(ctx.node)
                self.buffer.append(ctx.node)
                ctx.open(token,']')
            else:
                ctx.node = NodeArray(self.tokens,ctx.ptr,self)
                token.tag(ctx.node)
                self.buffer.append(ctx.node)
                ctx.open(token,']')
        elif token.t == '{':
            if len(self.buffer) and isinstance(self.buffer[-1],NodeName):
                struct = self.buffer.pop()
                ctx.node = NodeConstructor(self.tokens,ctx.ptr,self,struct)
                self.buffer.append(ctx.node)
                ctx.ptr -= 1
            else:
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self)
                self.buffer.append(ctx.node)
                ctx.open(token,'}')
        elif token.t == '<{':
            return ParseError.fromToken('Objects are not supported yet', token)
            ctx.open(token,'}>')
        elif token.t == 'fn':
            ctx.node = NodeFunction(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.buffer.append(ctx.node)
        elif token.t == 'if':
            ctx.node = NodeIf(self.tokens,ctx.ptr,self,(*((self.closeToken,) if type(self.closeToken) == str else self.closeToken),),handleParent=True,inBlock=False)
            token.tag(ctx.node)
            self.buffer.append(ctx.node)
        elif token.t == '<>':
            if len(self.buffer) and type(self.buffer[-1]) != Token:
                value = self.buffer.pop()
                ctx.node = NodeExpression(self.tokens,ctx.ptr,self,self.closeToken,handleParent=True,allowEmpty=False,isType=True)
                token.tag(ctx.node)
                self.buffer.append(NodeCast(self.tokens,ctx.ptr,self,value,ctx.node))
            else:
                return ParseError.fromToken('Expected expression before type cast', token)
        elif token.t == '<' and self.type:
            if len(self.buffer):
                value = self.buffer.pop()
                ctx.node = NodeTypeGeneric(self.tokens,ctx.ptr,self,value)
                self.buffer.append(ctx.node)
                ctx.open(token,'>')
            else:
                return ParseError.fromToken('Expected expression before generic arguments', token)
        elif token.t in ('<<','>>') and self.type:
            self.tokens.splitToken(token)
            ctx.ptr -= 1
        elif token.t == '=>' or token.t == '->':
            if len(self.buffer) and type(self.buffer[-1]) != Token:
                value = self.buffer.pop()
                ctx.node = NodeRefExpression(self.tokens,ctx.ptr,self,value,token.t=='=>')
                token.tag(ctx.node,'arrow')
                self.buffer.append(ctx.node)
            else:
                return ParseError.fromToken('Expected expression before reference expression', token)
        elif token.isidentifier():
            if token.t == 'struct':
                ctx.node = NodeStruct(self.tokens,ctx.ptr,self,allowUnnamed=True)
                token.tag(ctx.node)
                self.buffer.append(ctx.node)
            elif token.t == 'enum':
                ctx.node = NodeEnum(self.tokens,ctx.ptr,self,allowUnnamed=True)
                token.tag(ctx.node)
                self.buffer.append(ctx.node)
            else:
                n = NodeName(self.tokens,ctx.ptr,self,token.t)
                token.tag(n,'name')
                self.buffer.append(n)
        elif token.isnumeric():
            n = NodeNumber(self.tokens,ctx.ptr,self,token.t)
            token.tag(n,'number')
            self.buffer.append(n)
        elif token.isstring():
            n = NodeString(self.tokens,ctx.ptr,self,token.t[1:-1])
            token.tag(n,'string')
            self.buffer.append(n)
        elif token.t in operatorTokens:
            token.tag(self,'operator')
            self.buffer.append(token)
        elif type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        else:
            return ParseError.fromToken('Unexpected token', token)

class NodeDecorator( Node ):
    
    name : str
    args : list[NodeExpression]
    
    def __init__(self, tokens:Tokens, i:int, parent:Node):
        super().__init__(tokens,i,parent)
        self.name = None
        self.args = []
        self.arg = None
        self.inargs = False
        
    def feed(self, token:Token, ctx:ParseContext) -> ParseError | None:
        if self.name == None:
            if not token.isidentifier():
                raise ParseError.fromToken('Expected decorator name to be an identifier', token)
            self.name = token.t
            token.tag(self,'name')
        elif self.inargs == 0:
            if token.t == '(':
                token.tag(self)
                self.inargs = 1
                ctx.open(token,')')
            else:
                ctx.node = self.parent
                if token.t != ';':
                    ctx.ptr -= 1
        elif self.inargs == 1:
            if token.t in (',',')'):
                if self.arg != None:
                    self.args.append(self.arg)
                    self.arg = None
                if token.t == ')':
                    self.inargs = 2
                    ctx.close(token)
            else:
                ctx.node = NodeExpression(self.tokens,ctx.ptr,self,[',',')'],True,False)
                ctx.ptr -= 1
                self.arg = ctx.node
        elif self.inargs == 2:
            if token.t != ';':
                ctx.ptr -= 1
            ctx.node = self.parent
        else:
            raise Exception('That sould not have happened')      
  
class NodeRefExpression( Node ):
    """
    `... => (...)` reference operator
    """
    
    value      : Node
    expression : Union[NodeExpression,'NodeBlock']
    name       : Union[Token, None]
    ref        : bool
    takeResult : bool
    refToken   : Union[Token, None]
    
    def __init__(self, tokens:Tokens, i:int, parent:Node, value:Node, takeResult:bool):
        super().__init__(tokens,i,parent)
        self.value = value
        self.expression = None
        self.name = None
        self.ref = False
        self.takeResult = takeResult
        self.refToken = None
        
    def feed(self, token:Token, ctx:ParseContext) -> Union[ParseError,None]:
        if self.expression != None:
            if token.t not in (')','}'):
                return ParseError.fromToken('Something went horribly wrong', token)
            ctx.node = self.parent
        elif token.t == '(':
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,')',True,False,')')
            token.tag(ctx.node,'open')
            self.expression = ctx.node
            ctx.open(token,')')
        elif token.t == '{':
            ctx.node = NodeBlock(self.tokens,ctx.ptr,self,True)
            token.tag(ctx.node)
            self.expression = ctx.node
            ctx.open(token,'}')
        elif token.isidentifier() and self.name == None:
            self.tag(token,'name')
            self.name = token
        elif token.t == '&' and self.name == None and not self.ref:
            token.tag(self,'ref')
            self.ref = True
            self.refToken = token
        else:
            return ParseError.fromToken('Expected '+(('an identifier / ' + ('`&` / ' if not self.ref else '')) if self.name == None else '')+'`(` / `{`', token)
        
class NodeTypeGeneric( Node ):
    """
    `<...>` (generic) operator
    """
    
    value : Node
    args  : list['NodeExpression']
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, value:Node ):
        super().__init__(tokens,i,parent)
        self.value = value
        self.args = []
        self.idx = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if token.t == '>':
            token.tag(self)
            if self.idx:
                self.args.append(self.idx)
            ctx.close(token)
            ctx.node = self.parent
        elif token.t == ',':
            token.tag(self)
            self.args.append(self.idx or NodeExpression(self.tokens,self.i,self,(',','>'),handleParent=True,allowEmpty=True,isType=True))
            self.idx = None
        else:
            ctx.node = NodeExpression(self.tokens,self.i,self,(',','>'),handleParent=True,allowEmpty=True,isType=True)
            self.idx = ctx.node
            ctx.ptr -= 1

class NodeImport( Node ):
    """
    An import statement
    """
    
    names : list[str]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.names = []
        
    def feed( self, token:Token, ctx:ParseContext ):
        if token.isidentifier():
            self.names.append(token.t)
        elif token.t == ';':
            ctx.node = self.parent
        elif token.t == ',':
            pass
        else:
            raise ParseError.fromToken('Expected import name or `,`',token)

class NodeLet( DecoratableNode ):
    """
    A variable declaration
    """
    
    name      : str
    expr      : NodeExpression
    modifiers : set[str]
    type      : Union[NodeExpression,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.n = 0
        self.name = None
        self.expr = None
        self.modifiers = set()
    
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        # Name or modifier
        if self.n == 0:
            if token.isidentifier():
                if token.t in ('const','mut'):
                    if token.t in self.modifiers:
                        return ParseError.fromToken('Duplicate modifier', token)
                    token.tag(self,'mod')
                    mods = self.modifiers | { token.t }
                    incompatible = [
                        ('const','mut')
                    ]
                    for inc in incompatible:
                        if inc[0] in mods and inc[1] in mods:
                            other = inc[token.t == inc[0]]
                            return ParseError.fromToken('Modifier incompatible with `%s`'%(other,), token)
                    self.modifiers.add(token.t)
                    self.n -= 1
                else:
                    self.name = token.t
            else:
                return ParseError.fromToken('Expected an identifier', token)
        # Assignment, type hint or end of let statement
        elif self.n == 1:
            if token.t == '=':
                token.tag(self)
                ctx.node = NodeExpression(self.tokens,ctx.ptr+1,self,';',True)
                token.tag(ctx.node,'open')
                self.expr = ctx.node
            elif token.t == ':':
                token.tag(self)
                ctx.node = NodeExpression(self.tokens,ctx.ptr+1,self,(';','='),True,isType=True)
                token.tag(ctx.node,'open')
                self.type = ctx.node
                self.n -= 1
            elif token.t == ';':
                token.tag(self)
                ctx.node = self.parent
            else:
                return ParseError.fromToken('Expected one of `=:;`', token)
        # End of let statement
        elif self.n == 2:
            if token.t == ';':
                token.tag(self)
                ctx.node = self.parent
            else:
                return ParseError.fromToken('Expected `;`', token)
        else:
            return ParseError.fromToken('Invalid syntax', token)
        self.n += 1

class FunctionParameter:
    name    : str
    type    : Union[NodeExpression,None]
    default : Union[NodeExpression,None]
    
    def __init__(self, name:str, type_hint:Union[NodeExpression,None]=None, default:Union[NodeExpression,None]=None):
        self.name = name
        self.type = type_hint
        self.default = default
        
class NodeReturn( Node ):
    value : Union[NodeExpression,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.value = None
        self.tmp = False
    
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if token.t == ';':
            token.tag(self,'close')
            ctx.node = self.parent
        elif not self.tmp:
            self.tmp = True
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,';',True)
            self.value = ctx.node
            ctx.ptr -= 1
        else:
            return ParseError.fromToken('Expected an expression or `;`', token)
        
class NodeBreak( Node ):
    value : Union[NodeExpression,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.value = None
        self.tmp = False
    
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if token.t == ';':
            token.tag(self,'close')
            ctx.node = self.parent
        elif not self.tmp:
            self.tmp = True
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,';',True)
            self.value = ctx.node
            ctx.ptr -= 1
        else:
            return ParseError.fromToken('Expected an expression or `;`', token)
        
class NodeContinue( Node ):
    value : Union[NodeExpression,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.value = None
        self.tmp = False
    
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if token.t == ';':
            token.tag(self,'close')
            ctx.node = self.parent
        elif not self.tmp:
            self.tmp = True
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,';',True)
            self.value = ctx.node
            ctx.ptr -= 1
        else:
            return ParseError.fromToken('Expected an expression or `;`', token)

class NodeFunction( DecoratableNode ):
    name         : Union[str,None]
    body         : Union['NodeBlock',None]
    modifiers    : set[str]
    pararameters : list[FunctionParameter]
    type         : Union[NodeExpression,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.n = 0
        self.buffer = {}
        self.name = None
        self.body = None
        self.type = None
        self.modifiers = set()
        self.pararameters = []
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.n == 0: # Function name + modifiers
            if token.isidentifier():
                token.tag(self,'name')
                self.name = token.t
            elif token.t == '(':
                self.name = None
                ctx.ptr -= 1
            else:
                return ParseError.fromToken('Expected an identifier', token)
        elif self.n == 1: # `(` before parameters
            if token.t != '(':
                return ParseError.fromToken('Expected `(`', token)
        elif self.n == 2: # Parameters
            if token.t == ')':
                if len(self.buffer):
                    self.pararameters.append(FunctionParameter(**self.buffer))
                self.n += 1
            elif token.t == ',':
                if len(self.buffer):
                    self.pararameters.append(FunctionParameter(**self.buffer))
                    self.buffer = {}
                else:
                    return ParseError.fromToken('Expected parameter declaration', token)
            elif 'name' not in self.buffer:
                if token.isidentifier():
                    self.buffer['name'] = token.t
                else:
                    return ParseError.fromToken('Expected an identifier or `)`', token)
            elif 'type_hint' not in self.buffer:
                if token.t == ':':
                    ctx.node = NodeExpression(self.tokens,ctx.ptr+1,self,(',',')'),True,isType=True)
                    token.tag(ctx.node,'open')
                    self.buffer['type_hint'] = ctx.node
                elif token.t == '=':
                    self.buffer['type_hint'] = None
                    ctx.ptr -= 1
                else:
                    return ParseError.fromToken('Expected one of `:=,)`', token)
            elif 'default' not in self.buffer:
                if token.t == '=':
                    ctx.node = NodeExpression(self.tokens,ctx.ptr,self,(')',','),allowEmpty=False,handleParent=True)
                    self.buffer['default'] = ctx.node
                else:
                    return ParseError.fromToken('Expected one of `=,)`', token)
            else:
                return ParseError.fromToken('Expected `,` or `)`', token)
            self.n -= 1
        elif self.n == 3: # Type hint or body
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,handleParent=True)
                self.body = ctx.node
                ctx.open(token,'}')
            elif token.t == '->' and self.type == None:
                token.tag(self)
                ctx.node = NodeExpression(self.tokens,ctx.ptr+1,self,('{',';'),True,isType=True)
                self.type = ctx.node
                self.n -= 1
            elif token.t == ';':
                ctx.node = self.parent
            else:
                return ParseError.fromToken('Expected one of `{`, `;`'+(', `->`' if self.type == None else ''), token)
        elif self.n == 4:
            ctx.node = self.parent
        self.n += 1

class NodeIf( Node ):
    """
    An if statement
    """
    
    condition  : NodeExpression
    expression : Union[NodeExpression,'NodeBlock']
    otherwise  : Union[NodeExpression,'NodeBlock',None]
    
    def __init__ (self, tokens:Tokens, i:int, parent:Node, closeTokens:list[str]=None, handleParent:bool=False, inBlock:bool=True ):
        super().__init__(tokens,i,parent)
        self.closeTokens = closeTokens
        self.handleParent = handleParent
        self.inBlock = inBlock
        self.condition = None
        self.expression = None
        self.otherwise = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.inBlock:
            if self.condition == None:
                if token.t == '(':
                    ctx.node = NodeExpression(self.tokens,self.i,self,')',handleParent=True,allowEmpty=False,finishEnclose=')')
                    token.tag(ctx.node)
                    self.condition = ctx.node
                    ctx.open(token,')')
                else:
                    return ParseError.fromToken('Expected `(`', token)
            elif self.expression == None:
                if token.t == ')':
                    self.expression = False
                else:
                    return ParseError.fromToken('Expected `)`', token)
            elif self.expression == False:
                if token.t == '{':
                    ctx.node = NodeBlock(self.tokens,self.i,self,handleParent=False)
                    token.tag(ctx.node,'open')
                    ctx.open(token,'}')
                else:
                    # ctx.node = NodeExpression(self.tokens,self.i,self,';',handleParent=False,allowEmpty=True)
                    ctx.node = NodeBlock(self.tokens,ctx.ptr,self,False,True)
                    ctx.ptr -= 1
                self.expression = ctx.node
            elif self.otherwise == None:
                if token.t == 'else':
                    self.otherwise = False
                    token.tag(self)
                else:
                    ctx.node = self.parent
                    ctx.ptr -= 1
            elif self.otherwise == False:
                if token.t == '{':
                    ctx.node = NodeBlock(self.tokens,self.i,self,handleParent=False)
                    ctx.open(token,'}')
                elif token.t == 'if':
                    ctx.node = NodeIf(self.tokens,ctx.ptr,self,inBlock=True)
                    token.tag(ctx.node)
                    self.otherwise = ctx.node
                else:
                    # ctx.node = NodeExpression(self.tokens,self.i,self,';',handleParent=False,allowEmpty=True)
                    ctx.node = NodeBlock(self.tokens,ctx.ptr,self,False,True)
                    ctx.ptr -= 1
                self.otherwise = ctx.node
            else:
                ctx.ptr -= 1
                ctx.node = self.parent
        else:
            if self.condition == None:
                if token.t == '(':
                    ctx.node = NodeExpression(self.tokens,self.i,self,')',handleParent=True,allowEmpty=False,finishEnclose=')')
                    self.condition = ctx.node
                    ctx.open(token,')')
                else:
                    return ParseError.fromToken('Expected `(`', token)
            elif self.expression == None:
                if token.t == ')':
                    ctx.node = NodeExpression(self.tokens,self.i,self,'else',handleParent=True,allowEmpty=False)
                    self.expression = ctx.node
                else:
                    return ParseError.fromToken('Expected `)`', token)
            elif self.otherwise == None:
                if token.t == 'else':
                    token.tag(self)
                    ctx.node = NodeExpression(self.tokens,self.i,self,self.closeTokens,handleParent=True,allowEmpty=False)
                    token.tag(ctx.node,'open')
                    self.otherwise = ctx.node
                else:
                    return ParseError.fromToken('Expected `else`', token)
            else:
                if self.handleParent:
                    ctx.ptr -= 1
                ctx.node = self.parent

class NodeWhile( Node ):
    """
    A while loop
    """
    
    condition : NodeExpression
    body      : 'NodeBlock'
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.condition = None
        self.body = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.condition == None:
            if token.t == '(':
                ctx.node = NodeExpression(self.tokens,ctx.ptr,self,(')',),handleParent=False,allowEmpty=False,finishEnclose=')')
                token.tag(ctx.node)
                self.condition = ctx.node
                ctx.open(token,')')
            else:
                return ParseError.fromToken('Expected `(` before condition', token)
        elif self.body == None:
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self)
                token.tag(ctx.node)
                self.body = ctx.node
                ctx.open(token,'}')
            else:
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,singleElement=True)
                self.body = ctx.node
                ctx.ptr -= 1
        else:
            ctx.node = self.parent
            ctx.ptr -= 1
            
class NodeFor( Node ):
    """
    A for loop
    """
    
    name_it  : Token
    name_i   : Union[Token,None]
    iterable : NodeExpression
    body     : 'NodeBlock'
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.name_it = None
        self.name_i = None
        self.iterable = None
        self.body = None
        self.n = 0
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.n == 0:
            if not token.isidentifier():
                return ParseError.fromToken('Expected iterator name', token)
            self.name_it = token
            self.n = 1
        elif self.n == 1:
            if token.t == ',' and self.name_i == None:
                token.tag(self)
                self.name_i = self.name_it
                self.n = 0
            elif token.t == 'in':
                ctx.node = NodeExpression(self.tokens,ctx.ptr+1,self,'{',True,False)
                token.tag(self)
                self.iterable = ctx.node
                self.n = 2
            elif token.t == ':':
                return ParseError.fromToken('Type hint on for loop iterator is not currently supported', token)
            else:
                return ParseError.fromToken('Expected `in`', token)
        elif self.n == 2:
            self.name_it.tag(self,'name_it')
            if self.name_i != None:
                self.name_i.tag(self,'name_i')
            if token.t != '{':
                return ParseError.fromToken('Something went horribly wrong', token)
            ctx.node = NodeBlock(self.tokens,ctx.ptr,self,True)
            self.body = ctx.node
            ctx.open(token,'}')
            self.n = 3
        elif self.n == 3:
            if token.t != '}':
                return ParseError.fromToken('Something went horribly wrong', token)
            ctx.node = self.parent
            
class NodeConstructor( Node ):
    """
    A struct/class constructor
    """
    
    struct      : NodeExpression
    constructor : 'NodeBlock'
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, struct:NodeExpression ):
        super().__init__(tokens,i,parent)
        self.struct = struct
        self.constructor = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.constructor == None:
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,handleParent=True,singleElement=False)
                token.tag(ctx.node)
                self.constructor = ctx.node
                ctx.open(token,'}')
            else:
                return ParseError.fromToken('Expected `{`', token)
        else:
            ctx.node = self.parent

class NodeStruct( Node ):
    """
    A struct declaration
    """
    
    name : str
    body : 'NodeBlock'
        
    def __init__( self, tokens:Tokens, i:int, parent:Node, allowUnnamed:bool=False ):
        super().__init__(tokens,i,parent)
        self.allowUnnamed = allowUnnamed
        self.name = None
        self.unnamed = False
        self.body = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.name == None and not self.unnamed:
            if token.isidentifier():
                token.tag(self,'name')
                self.name = token.t
            elif token.t == '{' and self.allowUnnamed:
                self.unnamed = True
                ctx.ptr -= 1
            else:
                return ParseError.fromToken('Expected identifier', token)
        elif self.body == None:
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,handleParent=True)
                token.tag(ctx.node)
                self.body = ctx.node
                ctx.open(token,'}')
            else:
                return ParseError.fromToken('Expected `{`', token)
        else:
            ctx.node = self.parent

class NodeEnumMember( Node ):
    """
    An enum member declaration
    """
    
    name : str
    type : Literal['unary', 'tuple', 'struct']
    data : dict[str,]
    
    def __init__( self, tokens:Token, i:int, parent:Node, crepr:bool=False ):
        super().__init__(tokens,i,parent)
        self.name = None
        self.type = None
        self.data = None
        self.tmp = None
        self.st = 0
        self.crepr = crepr
        
    def feed(self, token: Token, ctx: ParseContext) -> Union[ParseError, None]:
        if self.name == None:
            if not token.isidentifier():
                return ParseError.fromToken('Expected identifier', token)
            token.tag(self, 'name')
            self.name = token.t
        elif self.type == None:
            if token.t in (';', ',', '}'):
                if token.t == '}':
                    ctx.ptr -= 1
                self.type = 'unary'
                self.data = None
                ctx.node = self.parent
            elif token.t == '(':
                if self.crepr:
                    return ParseError.fromToken('Tuples are not allowed for crepr', token)
                ctx.open(token,')')
                self.type = 'tuple'
                self.data = []
            elif token.t == '{':
                if self.crepr:
                    return ParseError.fromToken('Structs are not allowed for crepr', token)
                ctx.open(token,'}')
                self.type = 'struct'
                self.data = {}
            else:
                # TODO: better message, lol
                return ParseError.fromToken('Unexpected token', token)
        else:
            if self.type == 'struct':
                if self.st == 0:
                    if token.t in (',', ';', '}'):
                        if token.t == '}':
                            ctx.close(token)
                            ctx.node = self.parent
                    else:
                        if not token.isidentifier():
                            return ParseError.fromToken('Expected identifier', token)
                        self.tmp = [token, None]
                        self.st += 1
                elif self.st == 1:
                    if token.t != ':':
                        return ParseError.fromToken('Expected  `:`')
                    ctx.node = NodeExpression(self.tokens, ctx.ptr+1, self, [',',';','}'], True, isType=True)
                    self.tmp[1] = ctx.node
                    self.st += 1
                else:
                    self.data[self.tmp[0].t] = self.tmp[1]
                    if token.t == '}':
                        ctx.close(token)
                        ctx.node = self.parent
                    else:
                        self.st = 0
                    self.tmp = None
            if self.type == 'tuple':
                if token.t in (',', ';', ')'):
                    if token.t == ')':
                        ctx.close(token)
                        ctx.node = self.parent
                else:
                    ctx.node = NodeExpression(self.tokens, ctx.ptr, self, [',',';',')'], True, isType=True)
                    ctx.ptr -= 1
                    self.data.append(ctx.node)

class NodeEnum( Node ):
    """
    An enum declaration
    """
    
    name    : str
    members : list[NodeEnumMember]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, allowUnnamed:bool=False ):
        super().__init__(tokens,i,parent)
        self.allowUnnamed = allowUnnamed
        self.name = None
        self.unnamed = False
        self.members = None
        self.crepr = False
        
    def feed( self, token:Token, ctx:ParseContext ):
        if self.name == None and not self.unnamed:
            if token.isidentifier():
                token.tag(self,'name')
                self.name = token.t
            elif token.isstring() and token.t[1:-1] == 'C':
                self.crepr = True
            elif token.t == '{' and self.allowUnnamed:
                self.unnamed = True
                ctx.ptr -= 1
            else:
                return ParseError.fromToken('Expected identifier', token)
        elif self.members == None:
            if token.t != '{':
                return ParseError.fromToken('Expected `{`', token)
            ctx.open(token,'}')
            self.members = []
        else:
            if token.t in (';', ','):
                pass
            elif token.isidentifier():
                ctx.node = NodeEnumMember(self.tokens,ctx.ptr,self,self.crepr)
                self.members.append(ctx.node)
                ctx.ptr -= 1
            elif token.t == '}':
                ctx.close(token)
                ctx.node = self.parent

class NodeStructProp( Node ):
    """
    A struct property declaration
    """
    
    name : str
    type : NodeExpression
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, name:str, hint:NodeExpression ):
        super().__init__(tokens,i,parent)
        self.name = name
        self.type = hint
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        ctx.node = self.parent
        ctx.ptr -= 1
        
class NodeArray( Node ):
    """
    An array
    """
    
    items : list[NodeExpression]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.items = []
        self.item = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if token.t == ']':
            token.tag(self,'close')
            if self.item:
                self.items.append(self.item)
            ctx.close(token)
            ctx.node = self.parent
        elif token.t == ',':
            token.tag(self)
            self.items.append(self.item or NodeExpression(self.tokens,self.i,self,(',',']'),handleParent=True,allowEmpty=True))
            self.item = None
        else:
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,(',',']'),handleParent=True,allowEmpty=True)
            self.item = ctx.node
            ctx.ptr -= 1
        
class NodeBlock( Node ):
    children : list['Node']
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, handleParent:bool=False, singleElement:bool=False ):
        super().__init__(tokens,i,parent)
        self.children = []
        self.handleParent = handleParent
        self.singleElement = singleElement
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if len(self.children) > 0 and any(isinstance(node,NodeDecorator) for node in self.children) and not isinstance(self.children[-1],NodeDecorator):
            node = self.children.pop()
            i = 0
            while not isinstance(self.children[i],NodeDecorator):
                i += 1
            decs = [self.children.pop(i) for _ in range(len(self.children)-i)]
            if isinstance(node,DecoratableNode):
                node.add_decorators(*decs)
            self.children.append(node)
        if len(self.children) >= 1 and self.singleElement:
            ctx.node = self.parent
            ctx.ptr -= 1
        elif token.t == ';':
            token.tag(self)
        elif token.t == '{':
            ctx.node = NodeBlock(self.tokens,ctx.ptr,self)
            token.tag(ctx.node,'open')
            self.children.append(ctx.node)
            ctx.open(token,'}')
        elif token.t == '}':
            token.tag(self,'close')
            if self.parent:
                ctx.close(token)
            ctx.node = self.parent
            if self.handleParent:
                ctx.ptr -= 1
        elif token.t == '@':
            ctx.node = NodeDecorator(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'let':
            ctx.node = NodeLet(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'if':
            ctx.node = NodeIf(self.tokens,ctx.ptr,self,inBlock=True)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'fn':
            ctx.node = NodeFunction(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'return':
            ctx.node = NodeReturn(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'break':
            ctx.node = NodeBreak(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'continue':
            ctx.node = NodeContinue(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'while':
            ctx.node = NodeWhile(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'for':
            ctx.node = NodeFor(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'struct':
            ctx.node = NodeStruct(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'import':
            ctx.node = NodeImport(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif token.t == 'enum':
            ctx.node = NodeEnum(self.tokens,ctx.ptr,self)
            token.tag(ctx.node)
            self.children.append(ctx.node)
        elif type(token.t) == TokenEOF:
            if self.parent != None:
                return ParseError.fromToken('Unexpected EOF', token)
        elif token.isidentifier() and isinstance(self.parent,NodeStruct) and ctx.tokens.tokens[ctx.ptr+1].t == ':':
            hint = NodeExpression(self.tokens,ctx.ptr+2,None,';',handleParent=False,allowEmpty=True,isType=True)
            prop = NodeStructProp(self.tokens,ctx.ptr,self,token.t,hint)
            hint.parent = prop
            ctx.tokens.tokens[ctx.ptr+1].tag(hint,'open')
            token.tag(prop,'name')
            self.children.append(prop)
            ctx.node = hint
            ctx.ptr += 1
        else:
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,(';',) if self.singleElement or self.parent == None else (';','}'),handleParent=True,allowEmpty=True)
            self.children.append(ctx.node)
            ctx.ptr -= 1
        
def parse( tokens:Tokens ) -> Union[Node,ParseError]:
    root = NodeBlock(tokens,0,None,())    # the root token of the AST
    ctx = ParseContext( tokens, root, 0 ) # the parsing context
    while ctx.ptr < len(ctx.tokens.tokens):
        # feeds the current node with the current token
        err = None
        try:
            err = ctx.node.feed( ctx.tokens.tokens[ctx.ptr], ctx )
        except ParseError as e:
            err = e
        # returns an error if the parsing resulted in one
        if isinstance(err,ParseError): 
            node = ctx.node
            while node != root:
                err.trace.append(node)
                node = node.parent
            return err
        # moves on to the next token
        ctx.ptr += 1
    # Checks for unclosed brackets
    if len(ctx.enclose):
        tk = ctx.enclose[0].start
        return ParseError.fromToken('Missmatched `%s`' % (tk.t,), tk)
    # Checks for unclosed nodes
    if root != ctx.node:
        tk = ctx.node.tokens.tokens[ctx.node.i]
        return ParseError.fromToken('Unexpected end of input', tk)
    return root

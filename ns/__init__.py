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
    
    def __init__( self, t:str, c:int, l:int, i:int, s:Source ):
        self.t = t
        self.c = c
        self.l = l
        self.i = i
        self.s = s
    
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
]

operators: list[dict[str,Union[Literal['prefix'],Literal['binary'],Literal['postfix']]]] = [
    {
        '++' : 'postfix',
        '--' : 'postfix',
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
    
    l,c = 0,0
    
    flags: dict[str,dict[str,Any]] = {}
    
    tmp = ''
    
    def sep(i,dooff=True):
        nonlocal tmp
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
                    sep(i)
                    tmp = t
                    sep(i,False)
                    skip = len(t)-1
                    compound = True
            if not compound:
                if ch in ' \t\n':
                    sep(i)
                elif ch in '.,:;\/+-*=!?()[]\{\}<>@#~^&\\|':
                    sep(i)
                    tmp = ch
                    sep(i,False)
                elif ch in '`\'"':
                    flags['str'] = {'opens':ch,'c':c,'l':l,'i':i}
                else:
                    tmp += ch
        c += 1
        if ch == '\n':
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

class ParseError:
    """
    Holds data about a parser (syntax) error
    """
    
    message : str
    l       : int
    c       : int
    s       : int
    source  : Source
    
    def __init__( self, message:str, l:int, c:int, s:int, source:str ):
        self.message = message
        self.l = l
        self.c = c
        self.s = s
        self.source = source
        
    def __str__( self ) -> str:
        rline = self.source.body.splitlines(False)[self.l]
        line = rline.lstrip()     # removes all indent
        dl = len(rline)-len(line) # computes the shift caused by the indent
        return '\x1b[31;1mSyntax error\x1b[22;39m (\x1b[36m%s:%d:%d\x1b[39m):\n  %s\n\n  %s\n  %s' % (self.source.name,self.l+1,self.c+1,self.message.replace('\n','\n  '),line[:self.c-dl]+'\x1b[33m'+line[self.c-dl:self.c-dl+self.s]+'\x1b[39m'+line[self.c-dl+self.s:],' '*(self.c-dl)+'^'+'~'*(self.s-1))
    
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
    flags    : tuple[str]
    
    def __init__( self, tokens:Tokens, i:int, parent:'Node', flags:tuple[str] ):
        self.tokens = tokens
        self.i = i
        self.parent = parent
        self.flags = flags
        
    def feed( self, token:Token, _ctx:ParseContext ) -> Union[ParseError,None]:
        """
        Called whenever the parser is processing a token inside of a node
        """
        return ParseError.fromToken('Something went very wrong right before here :/ Can\'t tell much more', token)

class NodeName( Node ):
    """
    Reference to a variable
    """
    
    name : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str], name:str ):
        super().__init__(tokens,i,parent,flags)
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
    
    def __init__(self,tokens:Tokens,i:int,parent:Node,value:str):
        super().__init__(tokens,i,parent)
        self.value = value

class NodeAccessDot( Node ):
    """
    `.` accessor
    """
    
    node : Node
    prop : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str], node:Node, prop:str ):
        super().__init__(tokens,i,parent,flags)
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
            if self.idx:
                self.index.append(self.idx)
            if len(ctx.enclose) and ctx.enclose[-1].end == token.t:
                ctx.enclose.pop()
            else:
                return ParseError.fromToken('Missmatched `%s`'%(self.closeToken,), token)
            ctx.node = self.parent
        elif token.t in (',',':'):
            self.sep = self.sep or token.t
            self.index.append(self.idx or NodeExpression(self.tokens,self.i,self,(*((self.sep,) if self.sep != None else (',',':')),']'),handleParent=True,allowEmpty=True))
            self.idx = None
        else:
            ctx.node = NodeExpression(self.tokens,self.i,self,(*((self.sep,) if self.sep != None else (',',':')),']'),handleParent=True,allowEmpty=True)
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
            # Adds the last argument to the arguments list (if any)
            if self.arg:
                self.args.append(self.arg)
            # Ensures that no bracket was opened in the arguments and left unclosed
            if len(ctx.enclose) and ctx.enclose[-1].end == token.t:
                ctx.enclose.pop()
            else:
                return ParseError.fromToken('Missmatched `%s`'%(self.closeToken,), token)
            ctx.node = self.parent
        # Adds the previous argument to the argument list, allowing empty arguments
        elif token.t == ',':
            self.args.append(self.arg or NodeExpression(self.tokens,self.i,self,self.flags,(',',')'),handleParent=True,allowEmpty=True))
            self.arg = None
        # Creates a new argument
        else:
            ctx.node = NodeExpression(self.tokens,self.i,self,self.flags,(',',')'),handleParent=True,allowEmpty=True)
            self.arg = ctx.node
            # Makes sure that the expression also catches the first token
            ctx.ptr -= 1

class NodeOperatorPrefix( Node ):
    """
    Prefix operator
    """
    
    op    : Token
    value : 'NodeExpression'
    
    def __init__(self,tokens:Tokens,i:int,parent:Node,op:Token,value:'NodeExpression'):
        super().__init__(tokens,i,parent)
        self.op = op
        self.value = value
    
class NodeOperatorPostfix( Node ):
    """
    Postfix / Suffix operator
    """
    
    op    : Token
    value : 'NodeExpression'
    
    def __init__(self,tokens:Tokens,i:int,parent:Node,op:Token,value:'NodeExpression'):
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
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str], op:Token, right:'NodeExpression', left:'NodeExpression' ):
        super().__init__(tokens,i,parent,flags)
        self.op = op
        self.left = left
        self.right = right
        
class NodeCast( Node ):
    """
    `... <> ...` (type cast) operator
    """
    
    value : 'NodeExpression'
    type  : 'NodeTypeHint'
    
    def __init__(self,tokens:Tokens,i:int,parent:Node,value:'NodeExpression',cast:'NodeTypeHint'):
        super().__init__(tokens,i,parent)
        self.value = value
        self.type = cast

class NodeExpression ( Node ):
    """
    An expression
    """
    
    expression    : Union[Node,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str], closeToken:tuple[str], handleParent:bool=False, allowEmpty:bool=False, finishEnclose:Union[str,None]=None ):
        """
        :param str closeToken: A string or list of string that should be used to close the expression
        :param bool handleParent: Whether the parsing should resume after (False) or at (True) the enclosing token
        :param bool allowEmpty: Whether the expression is allowed to be empty
        :param Union[str,None] finishEnclose: In the case of an expression that has a matching bracket, specifies the expected closing token
        """
        super().__init__(tokens,i,parent,flags)
        self.closeToken = closeToken
        self.handleParent = handleParent
        self.allowEmpty = allowEmpty
        self.finishEnclose = finishEnclose
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
                if len(ctx.enclose) and ctx.enclose[-1].end == self.finishEnclose:
                    ctx.enclose.pop()
                else:
                    return ParseError.fromToken('Missmatched `%s`'%(self.closeToken,), token)
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
                                self.buffer.insert(i,NodeOperatorPrefix(self.tokens,self.i,self,op,value))
                                i = 0
                        elif kind == 'binary':
                            if i < len(self.buffer)-1 and i > 0 and type(self.buffer[i-1]) != Token and type(self.buffer[i+1]) != Token:
                                right = self.buffer.pop(i-1)
                                op = self.buffer.pop(i-1)
                                left = self.buffer.pop(i-1)
                                self.buffer.insert(i-1,NodeOperatorBinary(self.tokens,self.i,self,self.flags,op,left,right))
                                i = 0
                        elif kind == 'postfix':
                            if ((i == len(self.buffer)-1 or type(self.buffer[i+1]) == Token) and i > 0) and type(self.buffer[i-1]) != Token:
                                value = self.buffer.pop(i-1)
                                op = self.buffer.pop(i-1)
                                self.buffer.insert(i-1,NodeOperatorPostfix(self.tokens,self.i,self,op,value))
                                i = 0
                        else:
                            return ParseError.fromToken('Invalid operation', v)
                    i += 1
            # Errors out if there are extra operators
            for v in self.buffer:
                if type(v) == Token:
                    return ParseError.fromToken('Unexpected token', v)
            # Errors out if there are multiple expressions inside of a single one
            if len(self.buffer) > 1:
                return ParseError.fromToken('Malformed expression', token)
            # Moves the pointer back in case of a handling parent so that it will also receive the closing token
            if self.handleParent:
                ctx.ptr -= 1
            self.expression = self.buffer[0] if len(self.buffer) else None
            ctx.node = self.parent
        # Dot and colon accessor operators
        elif len(self.buffer) > 0 and type(self.buffer[-1]) == Token and self.buffer[-1].t in ('.',':'):
            a = self.buffer.pop()
            if not token.isidentifier():
                return ParseError.fromToken('Expected identifier after `%s`'%(a.t,), token)
            v = None if len(self.buffer) == 0 else self.buffer.pop()
            self.buffer.append(NodeAccessDot(self.tokens,ctx.ptr,self,self.flags,v,token.t))
        # Dot and colon accessor operators
        elif token.t in ('.',':'):
            if len(self.buffer) > 0 and type(self.buffer[-1]) == Token :
                return ParseError.fromToken('Unexpected token', token)
            else:
                if len(self.buffer) > 0 or token.t == '.':
                    self.buffer.append(token)
                else:
                    return ParseError.fromToken('Missing expression before `%s`'%(token.t,), token)
        elif token.t == '(':
            # Call operator
            if len(self.buffer):
                value = self.buffer.pop()
                ctx.node = NodeCall(self.tokens,ctx.ptr,self,value)
                self.buffer.append(ctx.node)
                ctx.enclose.append(Enclosure(token,')'))
            # New expression
            else:
                ctx.node = NodeExpression(self.tokens,ctx.ptr,self,self.flags,')',allowEmpty=True,finishEnclose=')')
                self.buffer.append(ctx.node)
                ctx.enclose.append(Enclosure(token,')'))
        elif token.t == '[':
            # Indexing operator
            if len(self.buffer) and not isinstance(self.buffer[-1],Token):
                value = self.buffer.pop()
                ctx.node = NodeIndex(self.tokens,ctx.ptr,self,value)
                self.buffer.append(ctx.node)
                ctx.enclose.append(Enclosure(token,']'))
            else:
                return ParseError.fromToken('Arrays are not supported yet', token)
        elif token.t == '{':
            if len(self.buffer) and isinstance(self.buffer[-1],NodeName):
                struct = self.buffer.pop()
                ctx.node = NodeConstructor(self.tokens,ctx.ptr,self,self.flags,struct)
                self.buffer.append(ctx.node)
                ctx.ptr -= 1
            else:
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags)
                self.buffer.append(ctx.node)
                ctx.enclose.append(Enclosure(token,'}'))
        elif token.t == '<{':
            return ParseError.fromToken('Objects are not supported yet', token)
            ctx.enclose.append(Enclosure(token,'}>'))
        elif token.t == 'fn':
            ctx.node = NodeFunction(self.tokens,ctx.ptr,self)
            self.buffer.append(ctx.node)
        elif token.t == 'if':
            ctx.node = NodeIf(self.tokens,ctx.ptr,self,(*((self.closeToken,) if type(self.closeToken) == str else self.closeToken),),handleParent=True,inBlock=False)
            self.buffer.append(ctx.node)
        elif token.t == '<>':
            if len(self.buffer) and type(self.buffer[-1]) != Token:
                value = self.buffer.pop()
                ctx.node = NodeTypeHint(self.tokens,ctx.ptr,self,self.flags,self.closeToken,handleParent=True,allowEmpty=False)
                self.buffer.append(NodeCast(self.tokens,ctx.ptr,self,value,ctx.node))
            else:
                return ParseError.fromToken('Expected expression before type cast', token)
        elif token.isidentifier():
            self.buffer.append(NodeName(self.tokens,ctx.ptr,self,self.flags,token.t))
        elif token.isnumeric():
            self.buffer.append(NodeNumber(self.tokens,ctx.ptr,self,token.t))
        elif token.isstring():
            self.buffer.append(NodeString(self.tokens,ctx.ptr,self.tokens,token.t[1:-1]))
        elif token.t in operatorTokens:
            self.buffer.append(token)
        elif type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        else:
            return ParseError.fromToken('Unexpected token', token)
        
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
            if self.idx:
                self.args.append(self.idx)
            if len(ctx.enclose) and ctx.enclose[-1].end == token.t:
                ctx.enclose.pop()
            else:
                return ParseError.fromToken('Missmatched `%s`'%(self.closeToken,), token)
            ctx.node = self.parent
        elif token.t == ',':
            self.args.append(self.idx or NodeTypeHint(self.tokens,self.i,self,self.flags,(',','>'),handleParent=True,allowEmpty=True))
            self.idx = None
        else:
            ctx.node = NodeTypeHint(self.tokens,self.i,self,self.flags,(',','>'),handleParent=True,allowEmpty=True)
            self.idx = ctx.node
            ctx.ptr -= 1
        
class NodeTypeHint( Node ):
    """
    An type expression
    """

    expression    : Union[Node,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str], closeToken:tuple[str], handleParent:bool=False, allowEmpty:bool=False, finishEnclose:Union[str,None]=None ):
        """
        :param str closeToken: A string or list of string that should be used to close the type hint
        :param bool handleParent: Whether the parsing should resume after (False) or at (True) the enclosing token
        :param bool allowEmpty: Whether the type hint is allowed to be empty
        """
        super().__init__(tokens,i,parent,flags)
        self.closeToken = closeToken
        self.handleParent = handleParent
        self.allowEmpty = allowEmpty
        self.finishEnclose = finishEnclose
        self.n = 0
        self.buffer = []
        self.expression = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        # Checks if the current token is a closing token for the type hint
        if token.t == self.closeToken if type(self.closeToken) == str else token.t in self.closeToken:
            # Checks for unfinished accessor operators
            if len(self.buffer) > 0 and type(self.buffer[-1]) == Token and self.buffer[-1].t in ('.',':'):
                return ParseError.fromToken('Unexpected end of type hint after `%s`'%(self.buffer[-1].t,), token)
            # Checks for empty type hints
            if not self.allowEmpty and len(self.buffer) == 0:
                return ParseError.fromToken('Unexpected empty type hint', token)
            # Checks for surrounding brackets
            if self.finishEnclose:
                if len(ctx.enclose) and ctx.enclose[-1].end == self.finishEnclose:
                    ctx.enclose.pop()
                else:
                    return ParseError.fromToken('Missmatched `%s`'%(self.closeToken,), token)
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
                                self.buffer.insert(i,NodeOperatorPrefix(self.tokens,self.i,self,op,value))
                                i = 0
                        elif kind == 'binary':
                            if i < len(self.buffer)-1 and i > 0 and type(self.buffer[i-1]) != Token and type(self.buffer[i+1]) != Token:
                                right = self.buffer.pop(i-1)
                                op = self.buffer.pop(i-1)
                                left = self.buffer.pop(i-1)
                                self.buffer.insert(i-1,NodeOperatorBinary(self.tokens,self.i,self,self.flags,op,left,right))
                                i = 0
                        elif kind == 'postfix':
                            if ((i == len(self.buffer)-1 or type(self.buffer[i+1]) == Token) and i > 0) and type(self.buffer[i-1]) != Token:
                                value = self.buffer.pop(i-1)
                                op = self.buffer.pop(i-1)
                                self.buffer.insert(i-1,NodeOperatorPostfix(self.tokens,self.i,self,op,value))
                                i = 0
                        else:
                            return ParseError.fromToken('Invalid operation', v)
                    i += 1
            # Errors out if there are extra operators
            for v in self.buffer:
                if type(v) == Token:
                    return ParseError.fromToken('Unexpected token', v)
            # Errors out if there are multiple expressions inside of a single type hint
            if len(self.buffer) > 1:
                return ParseError.fromToken('Malformed type hint', token)
            # Moves the pointer back in case of a handling parent so that it will also receive the closing token
            if self.handleParent:
                ctx.ptr -= 1
            self.expression = self.buffer[0] if len(self.buffer) else None
            ctx.node = self.parent
        # Dot and colon accessor operators
        elif len(self.buffer) > 0 and type(self.buffer[-1]) == Token and self.buffer[-1].t in ('.',':'):
            a = self.buffer.pop()
            if not token.isidentifier():
                return ParseError.fromToken('Expected identifier after `%s`'%(a.t,), token)
            v = self.buffer.pop()
            self.buffer.append(NodeAccessDot(self.tokens,ctx.ptr,self,v,token.t))
        # Dot and colon accessor operators
        elif token.t in ('.',':'):
            if len(self.buffer) > 0 and type(self.buffer[-1]) == Token :
                return ParseError.fromToken('Unexpected token', token)
            else:
                if len(self.buffer) > 0:
                    self.buffer.append(token)
                else:
                    return ParseError.fromToken('Missing expression before `%s`'%(token.t,), token)
        elif token.t == '>>':
            self.tokens.splitToken(token)
            ctx.ptr -= 1
        elif token.t == '(':
            ctx.node = NodeTypeHint(self.tokens,ctx.ptr,self,self.flags,')',allowEmpty=True,finishEnclose=')')
            self.buffer.append(ctx.node)
            ctx.enclose.append(Enclosure(token,')'))
        elif token.t == '[':
            return ParseError.fromToken('Arrays are not supported yet', token)
        elif token.t == '<':
            if len(self.buffer):
                value = self.buffer.pop()
                ctx.node = NodeTypeGeneric(self.tokens,ctx.ptr,self,value)
                self.buffer.append(ctx.node)
                ctx.enclose.append(Enclosure(token,'>'))
            else:
                return ParseError.fromToken('Expected expression before generic arguments', token)
        elif token.isidentifier():
            self.buffer.append(NodeName(self.tokens,ctx.ptr,self,self.flags,token.t))
        elif token.isnumeric():
            self.buffer.append(NodeNumber(self.tokens,ctx.ptr,self,self.flags,token.t))
        elif token.isstring():
            self.buffer.append(NodeString(self.tokens,ctx.ptr,self,self.tokens,token.t[1:-1]))
        elif token.t in operatorTokens:
            self.buffer.append(token)
        elif type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        else:
            return ParseError.fromToken('Unexpected token', token)

class NodeLet( Node ):
    """
    A variable declaration
    """
    
    name      : str
    expr      : NodeExpression
    modifiers : set[str]
    type      : Union[NodeTypeHint,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str] ):
        super().__init__(tokens,i,parent,flags)
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
                if token.t in ('const',):
                    self.modifiers.add(token.t)
                    self.n -= 1
                else:
                    self.name = token.t
            else:
                return ParseError.fromToken('Expected an identifier', token)
        # Assignment, type hint or end of let statement
        elif self.n == 1:
            if token.t == '=':
                ctx.node = NodeExpression(self.tokens,ctx.ptr+1,self,self.flags,';',True)
                self.expr = ctx.node
            elif token.t == ':':
                ctx.node = NodeTypeHint(self.tokens,ctx.ptr+1,self,self.flags,(';','='),True)
                self.type = ctx.node
                self.n -= 1
            elif token.t == ';':
                ctx.node = self.parent
            else:
                return ParseError.fromToken('Expected one of `=:;`', token)
        # End of let statement
        elif self.n == 2:
            if token.t == ';':
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
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str] ):
        super().__init__(tokens,i,parent,flags)
        self.value = None
        self.tmp = False
    
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if token.t == ';':
            ctx.node = self.parent
        elif not self.tmp:
            self.tmp = True
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,self.flags,';',True)
            self.value = ctx.node
            ctx.ptr -= 1
        else:
            return ParseError.fromToken('Expected an expression or `;`', token)
        
class NodeFunction( Node ):
    name         : Union[str,None]
    body         : Union['NodeBlock',None]
    modifiers    : set[str]
    pararameters : list[FunctionParameter]
    type         : Union[NodeTypeHint,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str] ):
        super().__init__(tokens,i,parent,flags)
        self.n = 0
        self.buffer = {}
        self.name = None
        self.body = None
        self.type = None
        self.modifiers = set()
        self.pararameters = []
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if type(token.t) == TokenEOF:
            return ParseError.fromToken('Unexpected EOF', token)
        if self.n == 0: # Function name + modifiers
            if token.isidentifier():
                if token.t in ('static','inline'):
                    self.modifiers.add(token.t)
                    self.n -= 1
                else:
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
                    ctx.node = NodeTypeHint(self.tokens,ctx.ptr+1,self,self.flags,(',',')'),True)
                    self.buffer['type_hint'] = ctx.node
                elif token.t == '=':
                    self.buffer['type_hint'] = None
                    ctx.ptr -= 1
                else:
                    return ParseError.fromToken('Expected one of `:=,)`', token)
            elif 'default' not in self.buffer:
                if token.t == '=':
                    ctx.node = NodeExpression(self.tokens,ctx.ptr,self,self.flags,(')',','),allowEmpty=False,handleParent=True)
                    self.buffer['default'] = ctx.node
                else:
                    return ParseError.fromToken('Expected one of `=,)`', token)
            else:
                return ParseError.fromToken('Expected `,` or `)`', token)
            self.n -= 1
        elif self.n == 3: # Type hint or body
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags,handleParent=True)
                self.body = ctx.node
                ctx.enclose.append(Enclosure(token,'}'))
            elif token.t == '->':
                ctx.node = NodeTypeHint(self.tokens,ctx.ptr+1,self,self.flags,('{',),True)
                self.type = ctx.node
                self.n -= 1
            else:
                return ParseError.fromToken('Expected `{` or `->`', token)
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
                    ctx.node = NodeExpression(self.tokens,self.i,self,self.flags,')',handleParent=True,allowEmpty=False,finishEnclose=')')
                    self.condition = ctx.node
                    ctx.enclose.append(Enclosure(token,')'))
                else:
                    return ParseError.fromToken('Expected `(`', token)
            elif self.expression == None:
                if token.t == ')':
                    self.expression = False
                else:
                    return ParseError.fromToken('Expected `)`', token)
            elif self.expression == False:
                if token.t == '{':
                    ctx.node = NodeBlock(self.tokens,self.i,self,self.flags,handleParent=False)
                    ctx.enclose.append(Enclosure(token,'}'))
                else:
                    ctx.node = NodeExpression(self.tokens,self.i,self,self.flags,';',handleParent=False,allowEmpty=True)
                    ctx.ptr -= 1
                self.expression = ctx.node
            elif self.otherwise == None:
                if token.t == 'else':
                    self.otherwise = False
                else:
                    ctx.node = self.parent
                    ctx.ptr -= 1
            elif self.otherwise == False:
                if token.t == '{':
                    ctx.node = NodeBlock(self.tokens,self.i,self,self.flags,handleParent=False)
                    ctx.enclose.append(Enclosure(token,'}'))
                elif token.t == 'if':
                    ctx.node = NodeIf(self.tokens,ctx.ptr,self,inBlock=True)
                    self.otherwise = ctx.node
                else:
                    ctx.node = NodeExpression(self.tokens,self.i,self,self.flags,';',handleParent=False,allowEmpty=True)
                    ctx.ptr -= 1
                self.otherwise = ctx.node
            else:
                ctx.ptr -= 1
                ctx.node = self.parent
        else:
            if self.condition == None:
                if token.t == '(':
                    ctx.node = NodeExpression(self.tokens,self.i,self,self.flags,')',handleParent=True,allowEmpty=False,finishEnclose=')')
                    self.condition = ctx.node
                    ctx.enclose.append(Enclosure(token,')'))
                else:
                    return ParseError.fromToken('Expected `(`', token)
            elif self.expression == None:
                if token.t == ')':
                    ctx.node = NodeExpression(self.tokens,self.i,self,self.flags,'else',handleParent=True,allowEmpty=False)
                    self.expression = ctx.node
                else:
                    return ParseError.fromToken('Expected `)`', token)
            elif self.otherwise == None:
                if token.t == 'else':
                    ctx.node = NodeExpression(self.tokens,self.i,self,self.flags,self.closeTokens,handleParent=True,allowEmpty=False)
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
                ctx.node = NodeExpression(self.tokens,ctx.ptr,self,self.flags,(')',),handleParent=False,allowEmpty=False,finishEnclose=')')
                self.condition = ctx.node
                ctx.enclose.append(Enclosure(token,')'))
            else:
                return ParseError.fromToken('Expected `(` before condition', token)
        elif self.body == None:
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags,handleParent=False)
                self.body = ctx.node
                ctx.enclose.append(Enclosure(token,'}'))
            else:
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags,singleElement=True)
                self.body = ctx.node
                ctx.ptr -= 1
        else:
            ctx.node = self.parent
            
class NodeFor( Node ):
    """
    A for loop
    """
    
    init      : 'NodeBlock'
    condition : NodeExpression
    increment : 'NodeBlock'
    body      : NodeExpression
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str] ):
        super().__init__(tokens,i,parent,flags)
        self.init = None
        self.condition = None
        self.increment = None
        self.body = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.init == None:
            if token.t == '(':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags,singleElement=True)
                self.init = ctx.node
                ctx.enclose.append(Enclosure(self,')'))
            else:
                return ParseError.fromToken('Expected `(`', token)
        elif self.condition == None:
            ctx.ptr -= 1
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,self.flags,(';',),handleParent=False,allowEmpty=False)
            self.condition = ctx.node
        elif self.increment == None:
            ctx.ptr -= 1
            ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags,singleElement=True)
            self.increment = ctx.node
        elif self.body == None:
            if token.t == ';':
                self.body = False
            else:
                return ParseError.fromToken('Expected `;`', token)
        elif self.body == False:
            if token.t == ')':
                ctx.enclose.pop()
                self.body = True
            else:
                return ParseError.fromToken('Expected `)`', token)
        elif self.body == True:
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags,handleParent=False)
                self.body = ctx.node
                ctx.enclose.append(Enclosure(token,'}'))
            else:
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags,singleElement=True,handleParent=True)
                self.body = ctx.node
                ctx.ptr -= 1
        else:
            ctx.node = self.parent
            
class NodeConstructor( Node ):
    """
    A struct/class constructor
    """
    
    struct      : NodeExpression
    constructor : 'NodeBlock'
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str], struct:NodeExpression ):
        super().__init__(tokens,i,parent,flags)
        self.struct = struct
        self.constructor = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.constructor == None:
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags+('constructor',),handleParent=True,singleElement=False)
                self.constructor = ctx.node
                ctx.enclose.append(Enclosure(token,'}'))
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
        
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str] ):
        super().__init__(tokens,i,parent,flags)
        self.name = None
        self.body = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.name == None:
            if token.isidentifier():
                self.name = token.t
            else:
                return ParseError.fromToken('Expected identifier', token)
        elif self.body == None:
            if token.t == '{':
                ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags,handleParent=False)
                self.body = ctx.node
                ctx.enclose.append(Enclosure(token,'}'))
            else:
                return ParseError.fromToken('Expected `{`', token)
        else:
            ctx.node = self.parent
            
class NodeStructProp( Node ):
    """
    A struct property declaration
    """
    
    name : str
    type : NodeTypeHint
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str], name:str, hint:NodeTypeHint ):
        super().__init__(tokens,i,parent,flags)
        self.name = name
        self.type = hint
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        ctx.node = self.parent
        ctx.ptr -= 1

class NodeBlock( Node ):
    children : list['Node']
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, flags:tuple[str], handleParent:bool=False, singleElement:bool=False ):
        super().__init__(tokens,i,parent,flags)
        self.children = []
        self.handleParent = handleParent
        self.singleElement = singleElement
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if len(self.children) >= 1 and self.singleElement:
            ctx.node = self.parent
            ctx.ptr -= 1
        elif token.t == ';':
            pass
        elif token.t == '{':
            ctx.node = NodeBlock(self.tokens,ctx.ptr,self,self.flags)
            self.children.append(ctx.node)
            ctx.enclose.append(Enclosure(token,'}'))
        elif token.t == '}':
            if self.parent and len(ctx.enclose) and ctx.enclose[-1].end == '}':
                ctx.node = self.parent
                ctx.enclose.pop()
                if self.handleParent:
                    ctx.ptr -= 1
            else:
                return ParseError.fromToken('Missmatched `}`', token)
        elif token.t == 'let':
            ctx.node = NodeLet(self.tokens,ctx.ptr,self,self.flags)
            self.children.append(ctx.node)
        elif token.t == 'if':
            ctx.node = NodeIf(self.tokens,ctx.ptr,self,self.flags,inBlock=True)
            self.children.append(ctx.node)
        elif token.t == 'fn':
            ctx.node = NodeFunction(self.tokens,ctx.ptr,self,self.flags)
            self.children.append(ctx.node)
        elif token.t == 'return':
            ctx.node = NodeReturn(self.tokens,ctx.ptr,self,self.flags)
            self.children.append(ctx.node)
        elif token.t == 'while':
            ctx.node = NodeWhile(self.tokens,ctx.ptr,self,self.flags)
            self.children.append(ctx.node)
        elif token.t == 'for':
            ctx.node = NodeFor(self.tokens,ctx.ptr,self,self.flags)
            self.children.append(ctx.node)
        elif token.t == 'struct':
            ctx.node = NodeStruct(self.tokens,ctx.ptr,self,self.flags)
            self.children.append(ctx.node)
        elif type(token.t) == TokenEOF:
            if self.parent != None:
                return ParseError.fromToken('Unexpected EOF', token)
        elif token.isidentifier() and isinstance(self.parent,NodeStruct) and ctx.tokens.tokens[ctx.ptr+1].t == ':':
            hint = NodeTypeHint(self.tokens,ctx.ptr+2,None,self.flags,';',handleParent=False,allowEmpty=True)
            prop = NodeStructProp(self.tokens,ctx.ptr,self,self.flags,token.t,hint)
            hint.parent = prop
            self.children.append(prop)
            ctx.node = hint
            ctx.ptr += 1
        else:
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,self.flags,(';',) if self.singleElement else (';','}'),handleParent=True,allowEmpty=True)
            self.children.append(ctx.node)
            ctx.ptr -= 1
        
def parse( tokens:Tokens ) -> Union[Node,ParseError]:
    root = NodeBlock(tokens,0,None,())    # the root token of the AST
    ctx = ParseContext( tokens, root, 0 ) # the parsing context
    while ctx.ptr < len(ctx.tokens.tokens):
        # feeds the current node with the current token
        err = ctx.node.feed( ctx.tokens.tokens[ctx.ptr], ctx )
        # returns an error if the parsing resulted in one
        if isinstance(err,ParseError): return err
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

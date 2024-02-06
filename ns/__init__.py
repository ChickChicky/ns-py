from typing import Any, Union

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
    
class Token:
    """
    Represents a single token
    """
    
    t : str
    c : int
    l : int
    i : int
    s : Source
    
    def __init__( self, t:int, c:int, l:int, i:int, s:Source ):
        self.t = t
        self.c = c
        self.l = l
        self.i = i
        self.s = s
    
    def isidentifier( self ) -> bool:
        return len(self.t) > 0 and self.t[0].lower() in 'abcdefghijklmnopqrstuvwxyz_$'
    
    def isnumeric( self ) -> bool:
        return self.t.isnumeric()
    
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
        
def tokenize( source:Source ) -> Tokens:
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
            
    for i,ch in enumerate(source.body):
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
            if ch in ' \t\n':
                sep(i)
            elif ch in '.,:;\/+-*=!?()[]\{\}@#~^&\\|':
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
    children : list['Node']
    
    def __init__( self, tokens:Tokens, i:int, parent:'Node' ):
        self.tokens = tokens
        self.i = i
        self.parent = parent
        self.children = []
        
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
    
    def __init__(self,tokens:Tokens,i:int,parent:Node,name:str):
        super().__init__(tokens,i,parent)
        self.name = name

class NodeNumber( Node ):
    """
    Number litteral
    """
    
    value : Union[int,float]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, value:Union[int,float,str] ):
        super().__init__(tokens,i,parent)
        self.value = float(value) if type(value) == str else value

class NodeAccessDot( Node ):
    """
    `.` operator
    """
    
    node : Node
    prop : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, node:Node, prop:str ):
        super().__init__(tokens,i,parent)
        self.node = node
        self.prop = prop
        
class NodeAccessColon( Node ):
    """
    `:` operator
    """
    
    node : Node
    prop : str
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, node:Node, prop:str ):
        super().__init__(tokens,i,parent)
        self.node = node
        self.prop = prop
        
class NodeIndex( Node ):
    """
    `[]` (index) operator
    """
    
    value : Node             # the indexed value
    index : 'NodeExpression' # the index expression
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, value:Node, index:str ):
        super().__init__(tokens,i,parent)
        self.value = value
        self.index = index
        
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
            self.args.append(self.arg or NodeExpression(self.tokens,self.i,self,(',',')'),handleParent=True,allowEmpty=True))
            self.arg = None
        # Creates a new argument
        else:
            ctx.node = NodeExpression(self.tokens,self.i,self,(',',')'),handleParent=True,allowEmpty=True)
            self.arg = ctx.node
            # Makes sure that the expression also catches the first token
            ctx.ptr -= 1

class NodeExpression ( Node ):
    """
    An expression
    """
    
    n             : int
    value         : Node
    closeToken    : str
    handleParent  : bool
    buffer        : list[Union[Node,Token]]
    allowEmpty    : bool
    finishEnclose : Union[str,None]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node, closeToken:str, handleParent:bool=False, allowEmpty:bool=False, finishEnclose:Union[str,None]=None ):
        """
        :param str closeToken: A string or list of string that should be used to close the expression
        :param bool handleParent: Whether the parsing should resume after (False) or at (True) the enclosing token
        :param bool allowEmpty: Whether the expression is allowed to be empty
        :param Union[str,None] finishEnclosure: In the case of an expression that has a matching bracket, specifies the expected closing token
        """
        super().__init__(tokens,i,parent)
        self.closeToken = closeToken
        self.handleParent = handleParent
        self.allowEmpty = allowEmpty
        self.finishEnclose = finishEnclose
        self.n = 0
        self.value = None
        self.buffer = []
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        # Checks if the current token is a closing token for the expressions
        if token.t == self.closeToken if type(self.closeToken) == str else token.t in self.closeToken:
            # Checks for unfinished accessor operators
            if len(self.buffer) > 0 and type(self.buffer[-1]) == Token and self.buffer[-1].t in ('.',':'):
                return ParseError.fromToken('Unexpected end of expression after `%s`'%(self.buffer[-1].t,), token)
            # Checks for empty expression
            if not self.allowEmpty and len(self.buffer) == 0:
                return ParseError.fromToken('Unexpected empty expression', token)
            # Moves the pointer back in case of a handling parent so that it will also receive the closing token
            if self.handleParent:
                ctx.ptr -= 1
            # Checks for surrounding brackets
            if self.finishEnclose:
                if len(ctx.enclose) and ctx.enclose[-1].end == self.finishEnclose:
                    ctx.enclose.pop()
                else:
                    return ParseError.fromToken('Missmatched `%s`'%(self.closeToken,), token)
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
            if len(self.buffer) > 0 and type(self.buffer[-1]) == Token and self.buffer[-1].t in ('.',':'):
                return ParseError.fromToken('Esxpected identifier after `%s`'%(self.buffer[-1].t,), token)
            else:
                if len(self.buffer) > 0 and type(self.buffer[-1]) != Token:
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
                ctx.node = NodeExpression(self.tokens,ctx.ptr,self,')',allowEmpty=True,finishEnclose=')')
                self.buffer.append(ctx.node)
                ctx.enclose.append(Enclosure(token,')'))
        elif token.t == '[':
            # Indexing operator
            if len(self.buffer):
                value = self.buffer.pop()
                ctx.node = NodeExpression(self.tokens,ctx.ptr,self,']',allowEmpty=False,finishEnclose=']')
                self.buffer.append(NodeIndex(self.tokens,ctx.ptr,self,value,ctx.node))
                ctx.enclose.append(Enclosure(token,']'))
            # New array
            else:
                return ParseError.fromToken('Arrays are not supported yet', token)
        elif len(self.buffer) == 0:
            # Variable reference
            if token.isidentifier():
                self.buffer.append(NodeName(self.tokens,ctx.ptr,self,token.t))
            # Number litteral
            elif token.isnumeric():
                self.buffer.append(NodeNumber(self.tokens,ctx.ptr,self,token.t))
            else:
                return ParseError.fromToken('Unexpected token', token)
        else:
            return ParseError.fromToken('Unexpected token', token)

class NodeLet( Node ):
    n         : int
    name      : str
    expr      : NodeExpression
    modifiers : set[str]
    
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        self.n = 0
        self.name = None
        self.expr = None
        self.modifiers = set()
    
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        # Name or modifier
        if self.n == 0:
            if token.isidentifier():
                if token.t in ('const',):
                    self.modifiers.add(token.t)
                    self.n -= 1
                else:
                    self.name = token.t
            else:
                return ParseError.fromToken('Expected identifier or modifier', token)
        # Assignment, type hint or end of let statement
        elif self.n == 1:
            if token.t == '=':
                ctx.node = NodeExpression(self.tokens,ctx.ptr+1,self,';',True)
                self.children.append(ctx.node)
            elif token.t == ':':
                return ParseError.fromToken('Type hints are not supported yet', token)
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

class NodeBlock( Node ):
    def __init__( self, tokens:Tokens, i:int, parent:Node ):
        super().__init__(tokens,i,parent)
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if token.t == ';':
            pass
        # New block
        elif token.t == '{':
            ctx.node = NodeBlock(self.tokens,ctx.ptr,self)
            self.children.append(ctx.node)
            ctx.enclose.append(Enclosure(token,'}'))
        # End of blocks
        elif token.t == '}':
            # Makes sure the last opened bracket matches up
            if self.parent and len(ctx.enclose) and ctx.enclose[-1].end == '}':
                ctx.node = self.parent
                ctx.enclose.pop()
            else:
                return ParseError.fromToken('Missmatched `}`', token)
        # New let statement
        elif token.t == 'let':
            ctx.node = NodeLet(self.tokens,ctx.ptr,self)
            self.children.append(ctx.node)
        # New expression
        else:
            ctx.node = NodeExpression(self.tokens,ctx.ptr,self,';',False,True)
            self.children.append(ctx.node)
            ctx.ptr -= 1
        
def parse( tokens:Tokens ) -> Union[Node,ParseError]:
    root = NodeBlock(tokens,0,None)       # the root token of the AST
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

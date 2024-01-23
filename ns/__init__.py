from typing import Any, Union

class Source:
    name : str
    body : str
    
    def __init__(self,name:str,body:str):
        self.name = name
        self.body = body
        
    @staticmethod
    def fromFile(path:str) -> 'Source':
        body = ''
        with open(path,'rt') as file:
            body = file.read().replace('\r\n','\n')
        return Source(path,body)
    
class Token:
    t : str
    c : int
    l : int
    i : int
    s : Source
    
    def __init__(self,t:int,c:int,l:int,i:int,s:Source):
        self.t = t
        self.c = c
        self.l = l
        self.i = i
        self.s = s
    
    def isidentifier( self ) -> bool:
        return len(self.t) > 0 and self.t[0].lower() in 'abcdefghijklmnopqrstuvwxyz_$'

class Tokens:
    source : Source
    tokens : list[Token]
    
    def __init__(self,source:Source):
        self.source = source
        self.tokens = []
        
def tokenize(source:Source) -> Tokens:
    tokens = Tokens(source)
    
    l,c = 0,0
    
    flags: dict[str,dict[str,Any]] = {}
    
    tmp = ''
    
    def sep(i):
        nonlocal tmp
        if len(tmp):
            tokens.tokens.append(Token(tmp,c,l,i,source))
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
                sep(i)
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

class ParseContext:
    tokens  : Tokens
    ptr     : int
    node    : 'Node'
    enclose : list[Token]
    
    def __init__(self,tokens:Tokens,node:'Node',ptr:int=0):
        self.tokens = tokens
        self.node = node
        self.ptr = ptr
        self.enclose = []

class ParseError:
    message : str
    l       : int
    c       : int
    s       : int
    source  : Source
    
    def __init__(self,message:str,l:int,c:int,s:int,source:str):
        self.message = message
        self.l = l
        self.c = c
        self.s = s
        self.source = source
        
    def __str__(self) -> str:
        rline = self.source.body.splitlines(False)[self.l]
        line = rline.lstrip()
        dl = len(rline)-len(line)
        return '\x1b[31;1mSyntax error\x1b[22;39m (\x1b[36m%s:%d:%d\x1b[39m):\n  %s\n\n  %s\n  %s' % (self.source.name,self.l+1,self.c+1,self.message.replace('\n','\n  '),line[:self.c-dl]+'\x1b[33m'+line[self.c-dl:self.c-dl+self.s]+'\x1b[39m'+line[self.c-dl+self.s:],' '*(self.c-dl)+'^'+'~'*(self.s-1))
    
    @staticmethod
    def fromToken(msg:str,tk:Token) -> 'ParseError':
        return ParseError(msg, tk.l, tk.c, len(tk.t), tk.s)
        
class Node:
    tokens   : Tokens
    i        : int
    parent   : 'Node'
    children : list['Node']
    
    def __init__(self,tokens:Tokens,i:int,parent:'Node'):
        self.tokens = tokens
        self.i = i
        self.parent = parent
        self.children = []
        
    def feed(self,token:Token,_ctx:ParseContext) -> Union[ParseError,None]:
        return ParseError.fromToken('Something went very wrong right before here :/ Can\'t tell much more', token)

class NodeExpression ( Node ):
    n : int
    value : Node
    
    def __init__(self,tokens:Tokens,i:int,parent:Node):
        super().__init__(tokens,i,parent)
        self.n = 0
        self.value = None
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.n == 0:
            pass
        elif self.n == 1:
            if token.t == ';':
                ctx.node = self.parent
            else:
                return ParseError.fromToken('Unexpected token, expected `;`', token)
        else:
            return ParseError.fromToken('Invalid syntax', token)
        self.n += 1

class NodeLet ( Node ):
    n : int
    name : str
    expr : NodeExpression
    
    def __init__(self,tokens:Tokens,i:int,parent:Node):
        super().__init__(tokens,i,parent)
        self.n = 0
        self.name = None
        self.expr = None
    
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if self.n == 0:
            if token.isidentifier():
                self.name = token.t
            else:
                return ParseError.fromToken('Invalid token, expected identifier', token)
        elif self.n == 1:
            if token.t == '=':
                ctx.node = NodeExpression(self.tokens,ctx.ptr+1,self.parent)
                self.children.append(ctx.node)
            elif token.t == ':':
                return ParseError.fromToken('Type hints are not supported yet', token)
            elif token.t == ';':
                ctx.node = self.parent
            else:
                return ParseError.fromToken('Invalid token, expected one of `=:;`, got %s'%(token.t,), token)
        else:
            return ParseError.fromToken('Invalid syntax', token)
        self.n += 1

class NodeBlock ( Node ):
    
    def __init__(self,tokens:Tokens,i:int,parent:Node):
        super().__init__(tokens,i,parent)
        
    def feed( self, token:Token, ctx:ParseContext ) -> Union[ParseError,None]:
        if token.t == ';':
            pass
        elif token.t == '{':
            ctx.node = NodeBlock(self.tokens,ctx.ptr,self)
            self.children.append(ctx.node)
            ctx.enclose.append(token)
        elif token.t == '}':
            if self.parent and len(ctx.enclose) and ctx.enclose[-1].t == '{':
                ctx.node = self.parent
                ctx.enclose.pop()
            else:
                return ParseError.fromToken('Missmatched `}`', token)
        elif token.t == 'let':
            ctx.node = NodeLet(self.tokens,ctx.ptr,self)
            self.children.append(ctx.node)
        else:
            pass
        
def parse( tokens:Tokens ) -> Union[Node,ParseError]:
    root = NodeBlock(tokens,0,None)
    ctx = ParseContext( tokens, root, 0 )
    while ctx.ptr < len(ctx.tokens.tokens):
        err = ctx.node.feed( ctx.tokens.tokens[ctx.ptr], ctx )
        if isinstance(err,ParseError): return err
        ctx.ptr += 1
    if len(ctx.enclose):
        tk = ctx.enclose[0]
        return ParseError.fromToken('Missmatched `%s`' % (tk.t,), tk)
    return root

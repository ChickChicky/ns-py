import ns, sys

args = sys.argv[1:]

source = ns.Source.fromFile(args[0])

tokens = ns.tokenize( source )
# for tk in tokens.tokens:
#     print(' -> ',tk)
tree   = ns.parse( tokens )

# def explore(tree:ns.Node,indent:str=''):
#     print(indent+'\x1b[1;7m'+tree.__class__.__name__+'\x1b[m')
#     if isinstance(tree,ns.Node):
#         for k in tree.__annotations__:
#             if hasattr(tree,k):
#                 print(indent+'\x1b[36m'+k+'\x1b[39m \x1b[33m'+repr(getattr(tree,k))+'\x1b[39m')
#             else:
#                 print(indent+'\x1b[90m'+k+'\x1b[39m')
#         for n in tree.buffer if type(tree) == ns.NodeExpression else [tree.node] if type(tree) == ns.NodeAccessDot else [tree.value,tree.index] if type(tree) == ns.NodeIndex else [tree.value,*tree.args] if type(tree) == ns.NodeCall else [tree.name,*tree.children] if type(tree) == ns.NodeLet else tree.children:
#             explore(n,indent+'    ')
#     else:
#         print(indent+repr(tree))

def explore(tree) -> str:
    if isinstance(tree,ns.NodeExpression):
        return '\x1b[105;1m'+('T'if tree.type else 'E')+'\x1b[49;22m'+explore(tree.expression)
    elif isinstance(tree,(ns.Node,ns.FunctionParameter)):
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
        s = 'set{ '
        if len(tree): s += '\n'
        for v in tree:
            s += '  '+explore(v).replace('\n','\n  ')+'\x1b[39m\n'
        return s+'}'
    elif isinstance(tree,tuple):
        s = '( '
        for i,v in enumerate(tree):
            s += explore(v).replace('\n','\n  ')+'\x1b[39m'+(', ' if i < len(tree)-1 else '')
        s += ' )'
        return s
    elif isinstance(tree,dict):
        s = '{ '
        if len(tree): s += '\n  '
        for i,(k,v) in enumerate(tree.items()):
            s += k + ': ' + explore(v).replace('\n','\n  ')+'\x1b[39m'+(', '+('\n  ' if len(tree) else '') if i < len(tree)-1 else '')
        if len(tree): s += '\n'
        s += '}'
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
else:
    print(explore(tree))

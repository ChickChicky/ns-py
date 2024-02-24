import ns, sys

args = sys.argv[1:]

source = ns.Source.fromFile(args[0])

tokens = ns.tokenize( source )
# for tk in tokens.tokens:
#     print(' -> ',tk)
tree   = ns.parse( tokens )

def explore(tree:ns.Node,indent:str=''):
    print(indent+'\x1b[1;7m'+tree.__class__.__name__+'\x1b[m')
    if isinstance(tree,ns.Node):
        for k in tree.__annotations__:
            if hasattr(tree,k):
                print(indent+'\x1b[36m'+k+'\x1b[39m \x1b[33m'+repr(getattr(tree,k))+'\x1b[39m')
            else:
                print(indent+'\x1b[90m'+k+'\x1b[39m')
        for n in tree.buffer if type(tree) == ns.NodeExpression else [tree.node] if type(tree) == ns.NodeAccessDot else [tree.value,tree.index] if type(tree) == ns.NodeIndex else [tree.value,*tree.args] if type(tree) == ns.NodeCall else [tree.name,*tree.children] if type(tree) == ns.NodeLet else tree.children:
            explore(n,indent+'    ')
    else:
        print(indent+repr(tree))

if isinstance(tree,ns.ParseError):
    print(tree)
else:
    explore(tree)

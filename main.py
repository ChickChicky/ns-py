import ns, sys

args = sys.argv[1:]

source = ns.Source.fromFile(args[0])

tokens = ns.tokenize( source )
tree   = ns.parse( tokens )

def explore(tree:ns.Node,indent:str=''):
    print(indent+tree.__class__.__name__)
    for n in tree.children:
        explore(n,indent+'    ')

if isinstance(tree,ns.ParseError):
    print(tree)
else:
    explore(tree)

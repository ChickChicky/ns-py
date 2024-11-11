#!/usr/bin/env python3
import ns, sys
from time import time
from subprocess import call
from os import remove

args = sys.argv[1:]

if len(args) == 0:
    print('Missing source file')
    exit(1)
    
source = ns.Source.fromFile(args[0])

tokens = ns.tokenize( source )
tree   = ns.parse( tokens )

def transform( node: ns.Node ) -> str:
    if isinstance(node, ns.NodeExpression):
        return transform(node.expression)
    if isinstance(node, ns.NodeName):
        return node.name
    if isinstance(node, ns.NodeString):
        return '"'+repr(node.value)[1:-1]+'"'
    if isinstance(node, ns.NodeNumber):
        return str(node.value)
    s = ''
    if isinstance(node, ns.NodeBlock):
        root = node == tree
        if not root: s += '{'
        for child in node.children:
            s += transform(child)
            s += ';'
        if not root: s += '}'
    elif isinstance(node, ns.NodeFunction):
        s += (transform(node.type) if node.type else 'void') + ' ' + node.name + '('
        for param in node.pararameters:
            s += transform(param.type)
            s += param.name
        s += ')'
        s += transform(node.body)
    elif isinstance(node, ns.NodeCall):
        s += '('+transform(node.value)+')('
        for i, arg in enumerate(node.args):
            s += '('+(transform(arg))+')'
            if i < len(node.args)-1:
                s += ','
        s += ')'
    elif isinstance(node, ns.NodeReturn):
        return 'return('+transform(node.value)+')'
    else:
        raise TypeError(type(node).__name__)
    return s

if isinstance(tree,ns.ParseError):
    print(tree)
else:
    t = '#include <stdio.h>\n'
    t += transform(tree)
    m = hex(hash(time()))[2:]
    i = './_'+m+'.c'
    o = './_'+m
    with open(i,'wt') as f:
        f.write(t)
    try:
        if call(['cc', i, '-o', o]):
            exit(1)
        exit(call(o))
    finally:
        try:
            remove(i)
        except: pass
        try:
            remove(o)
        except: pass
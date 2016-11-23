# -*- coding: utf-8 -*-
"""
Created on Mon Nov 21 16:29:31 2016

@author: huang_cj2
"""

import sys, time

def test(func):
    try:
        print >>sys.stderr, func,
        exec(func)
        time.sleep(100)
    except KeyboardInterrupt:
        print >>sys.stderr, 'C'
    except SystemExit:
        print >>sys.stderr, 'E'

map(test, [
    "raise KeyboardInterrupt",
    "raise SystemExit",
    "sys.exit()",
    "print >>sys.stderr, 'Ctrl-C',"
])
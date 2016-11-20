#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, traceback

class CodingWrappedWriter:
    def __init__(self, coding, writer):
        self.flush = getattr(writer, 'flush', lambda : None)
        self.write = \
            lambda s: writer.write(s.decode(coding).encode(writer.encoding))

def eqaulUtf8(encoding):
    return encoding is None or encoding.lower() in ('utf8', 'utf-8', 'utf_8')

if eqaulUtf8(sys.stderr.encoding):
    utf8Stderr = sys.stderr
else:
    utf8Stderr = CodingWrappedWriter('utf8', sys.stderr)

levels = 'NULL', 'NOTIFY', 'CRITICAL', 'ERROR', 'WARN', 'INFO', 'DEBUG', 'DUMP'
    
def _log(slf, level, *message, **kwargs):
    slf.writer.write('[%s] %s ' % (level[:4], slf.name))
    if kwargs.get('exc_info', False):
        slf.writer.write('\n')
        traceback.print_exc(file=slf.writer)
    if level == 'DUMP':
        s = ' '.join(map(repr, message))
    else:        
        s = ' '.join(map(str, message))
    slf.writer.write(s)
    slf.writer.write('\n')

def _logUnboundedMethod(level):
    return lambda slf, *msg, **kwargs: _log(slf, level, *msg, **kwargs)

def _logBoundedMethod(slf, level):
    return lambda *msg, **kwargs: _log(slf, level, *msg, **kwargs)

_nullLog = lambda *args, **kwargs: None

_logUM = dict((level, _logUnboundedMethod(level)) for level in levels[1:])

def getClsAttr(bases, attrs, attrName):
    if attrName in attrs:
        return attrs[attrName]

    for base in bases:
        if hasattr(base, attrName):
            return getattr(base, attrName)

    raise AttributeError

# DO NOT use this metaclass directly, inherent 'Logger' instead.
class _LoggerMetaClass(type):
    def __new__(cls, name, bases, attrs):
        attrs['name'] = attrs.get('name', name)
        
        if name == 'Logger':
            attrs['level'] = 'DUMP'
            attrs['writer'] = utf8Stderr
            for level in levels[1:]:
                attrs[level.lower()] = _logUM[level]
            return type.__new__(cls, name, bases, attrs)
        
        if 'level' not in attrs:
            return type.__new__(cls, name, bases, attrs)

        clsLevel = attrs['level'].upper()
        attrs['level'] = clsLevel
        
        for base in bases:
            if hasattr(base, 'level'):
                baseLevel = getattr(base, 'level')
                break
        
        ic, ib = levels.index(clsLevel), levels.index(baseLevel)

        for level in levels[ic+1 : ib+1]:
            attrs[level.lower()] = _nullLog
        for level in levels[ib+1 : ic+1]:
            attrs[level.lower()] = _logUM[level]

        return type.__new__(cls, name, bases, attrs)

class Logger(object):
    __metaclass__ = _LoggerMetaClass

    def setLevel(self, level):
        level = level.upper()
        ib, ic = levels.index(self.level), levels.index(level)
        self.level = level    
        for level in levels[ic+1 : ib+1]:
            setattr(self, level.lower(), _nullLog)
        for level in levels[ib+1 : ic+1]:
            setattr(self, level.lower(), _logBoundedMethod(self, level))
    

def main():
    def test(l):
        print >>sys.stderr, '===', l.level, '==='
        l.notify(1)
        l.critical(2)
        l.error(3)
        l.warn(4)
        l.info(5)
        l.debug(6)
        l.dump(7)
        print >>sys.stderr

    l = Logger(); test(l);

    for level in levels:
        l.setLevel(level); test(l)
    
    for _level in levels:
        class MyLogger(Logger):
            level = _level
    
        l = MyLogger(); test(l)

if __name__ == '__main__':
    main()

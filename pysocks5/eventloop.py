# -*- coding: utf-8 -*-

import select
import time

EV_READ, EV_WRITE, EV_ERROR = range(3)
TIMEOUT = 5

class EventLoop:
    def __init__(self):
        self.timeout_callbacks = []
        self.event_callbacks = {}, {}, {}

    def run(self):
        while any(self.event_callbacks) or self.timeout_callbacks:
            if any(self.event_callbacks):
                rwx = select.select(
                    self.event_callbacks[EV_READ],
                    self.event_callbacks[EV_WRITE],
                    self.event_callbacks[EV_ERROR],
                    TIMEOUT
                )
                for ev, d in enumerate(self.event_callbacks):
                    for fd in rwx[ev]:
                        if fd in d:
                            func, args, kwargs = d[fd]
                            func(*args, **kwargs)
            
            if self.timeout_callbacks:
                unarrived, now = [], time.time()
                for t, func, args, kwargs in self.timeout_callbacks:
                    if now >= t:
                        func(*args, **kwargs)
                    else:
                        unarrived.append( (t, func, args, kwargs) )
                self.timeout_callbacks = unarrived

    def register(self, fd, ev, func, *args, **kwargs):
        self.event_callbacks[ev][fd] = func, args, kwargs

    def unregister(self, fd, ev):
        self.event_callbacks[ev].pop(fd, None)
    
    def unregister_all(self, fd):
        for d in self.event_callbacks:
            d.pop(fd, None)
    
    def is_register(self, fd, ev):
        return fd in self.event_callbacks[ev]
    
    def add_timeout(self, timeout, func, *args, **kwargs):
        now = time.time()
        self.timeout_callbacks.append( (timeout+now, func, args, kwargs) )

Loop = EventLoop()

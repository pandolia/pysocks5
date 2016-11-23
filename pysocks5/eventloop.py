# -*- coding: utf-8 -*-

import select
import time

EV_READ, EV_WRITE, EV_ERROR, EV_TIMEOUT, EV_STOP = range(5)

class EventLoop:
    def __init__(self):
        self.callbacks = [{} for i in range(5)]
        self.rwx_callbacks = self.callbacks[:3]
        self.timeout_callbacks = self.callbacks[EV_TIMEOUT]
        self.stop_callbacks = self.callbacks[EV_STOP]

    def run(self):
        self.running = True
        while self.running and any(self.callbacks):
            if any(self.rwx_callbacks):
                rwx = select.select(*self.rwx_callbacks)
                for ev, d in enumerate(self.rwx_callbacks):
                    for fd in rwx[ev]:
                        if fd in d:
                            d[fd]()
            for fd, value in self.timeout_callbacks.items():
                callback, t = value
                if time.time() >= t:
                    callback()
                    del self.timeout_callbacks[fd]
        else:
            for callback in self.stop_callbacks.values():
                callback()
    
    def stop(self):
        self.running = False

    # It is expected that no exception will be throwed in `callback`
    def register(self, fd, ev, callback, timeout=0):
        if ev != EV_TIMEOUT:
            self.callbacks[ev][fd] = callback
        else:
            self.callbacks[ev][fd] = callback, timeout+time.time()

    def unregister(self, fd, ev):
        self.callbacks[ev].pop(fd, None)
    
    def unregister_all(self, fd):
        [d.pop(fd, None) for d in self.callbacks]
    
    def is_register(self, fd, ev):
        return fd in self.callbacks[ev]

Loop = EventLoop()

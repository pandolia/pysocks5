#!/env/bin/python
# -*- coding: utf-8 -*-

import socket
import sys

from eventloop import EV_READ, EV_WRITE, EV_ERROR, EV_TIMEOUT, EV_STOP, Loop
from logger import Logger

# user defined methods' name convention:
#   Method -- public: callable, un-inheritable
#   method -- protected: un-callable, inheritable
#   _method -- private: un-callable, un-inheritable
# user defined attributes' name convention:
#   attribute -- readonly
#   _attribute -- hidden

class Socket(Logger):
    def __init__(self, sock, addr, tag='', event_loop=Loop):
        if sock is None:            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(0)
            sock.connect_ex(addr)
        
        self.fd = sock.fileno()
        self.name = '%s<%s:%d>' % (self.__class__.__name__, addr[0], addr[1])
        self.name += tag and ('-'+tag)
        self.sock = sock
        self.event_loop = event_loop
        self.read_buf = ''
        self.write_buf = []
        self.sock.setblocking(0)
        self.event_loop.register(self.fd, EV_READ, self._read)
        self.event_loop.register(self.fd, EV_WRITE, self._write)
        self.event_loop.register(self.fd, EV_ERROR, self._error)
        self.event_loop.register(self.fd, EV_STOP, self._destroy)
        self.closed = False
        self.info('created')

    def _read(self):
        try:
            data = self.sock.recv(4096)
        except socket.error:
            self._error()
        else:
            if data:
                self.read_buf = self.on_data(data, self.read_buf+data) or ''
            else:
                self.on_remote_close()
                self._destroy()

    def _write(self):
        if self.write_buf:
            data = ''.join(self.write_buf)
            try:
                n = self.sock.send(data)
            except socket.error:
                self._error()
            else:
                del self.write_buf[:]
                if n > 0:
                    sent, data = data[:n], data[n:]
                    self.on_sent(sent)
                if data:
                    self.write_buf.append(data)
                    return
        if self.closed:
            self.on_close()
            self._destroy()
    
    def _error(self):
        self.on_error()
        self._destroy()
    
    def _destroy(self):
        self.event_loop.unregister_all(self.fd)
        self.sock.close()
        self.on_destroy()

    def Close(self):
        self.closed = True
        if self.write_buf:
            self.event_loop.unregister(self.fd, EV_READ)
        else:
            self.on_close()
            self._destroy()
    
    def Send(self, data):
        if not self.closed and data:
            self.write_buf.append(data)
        
    def on_data(self, data, all_data):
        self.debug('recv', len(data), 'bytes')
        self.dump(data)
        return all_data
    
    def on_sent(self, data):
        self.debug('sent', len(data), 'bytes')
        self.dump(data)
    
    def on_error(self):
        self.error('encountered error')
    
    def on_remote_close(self):
        self.info('closed by remote')
    
    def on_close(self):    
        self.info('closed')
    
    def on_destroy(self):
        pass

def test_client(server_addr):
    s = 'GET / HTTP/1.1\r\nHost: {0}\r\nConnection: Close\r\n\r\n'

    class HttpClient(Socket):
        level = 'debug'

        def __init__(self, server_addr, i):
            Socket.__init__(self, None, server_addr, str(i))
            self.Send(s.format(server_addr[0]))
        
        def on_destroy(self):
            resp = repr(self.read_buf[:20] + ' ... ' + self.read_buf[-20:])
            self.debug('destroyed. received:', resp)

    for i in range(3):
        HttpClient(server_addr, i)
    
    # uncomment this line, we will find that `on_destroy` will be called
    # anyway even if we stopped the `Loop` early.
    # Loop.register(-1, EV_TIMEOUT, Loop.stop, 0.01)

    Loop.run()

class Server(Logger):
    def __init__(self, server_addr, connection_handler=None, num_listens=10):
        self.name = self.__class__.__name__ + ('<%s:%d>' % server_addr)
        self.addr = server_addr
        self.connection_handler = connection_handler or self.handle
        self.num_listens = num_listens
    
    def Run(self, event_loop=Loop):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setblocking(0)
            self.sock.bind(self.addr)
            self.sock.listen(self.num_listens)
        except socket.error as e:
            self.on_failed_to_start(e)
        else:
            fd = self.sock.fileno()
            event_loop.register(fd, EV_READ, self._accept)
            event_loop.register(fd, EV_ERROR, self._error)
            event_loop.register(fd, EV_STOP, self._destroy)
            self.fd = fd
            self.event_loop = event_loop
            self.Stop = event_loop.stop
            self.on_start()

            event_loop.run()

    def _accept(self):
        try:
            client_sock, client_addr = self.sock.accept()
        except socket.error:
            self._error()
        else:
            # It is expected that no exception will be throwed
            # in `self.connection_handler`
            self.connection_handler(client_sock, client_addr, self)
    
    def _error(self):
        self.on_error()
        self._destroy()
    
    def _destroy(self):
        self.event_loop.unregister_all(self.fd)
        self.sock.close()
        self.on_destroy()
    
    def on_failed_to_start(self, e):
        self.critical('failed to start')
        sys.exit(1)
    
    def on_start(self):
        self.info('started')
    
    def on_error(self):
        self.error('encountered error')
    
    def on_destroy(self):
        self.info('destroyed')
    
    # used to replace `connection_handler` when it is not provided
    def handle(self, client_sock, client_addr, event_loop, server_obj):
        raise NotImplemented

def test_server(server_addr):

    class HttpClientHandler(Socket):
        level = 'debug'

        def __init__(self, sock, addr, server_obj):
            Socket.__init__(self, sock, addr, '', server_obj.event_loop)
            self.response = (
                'HTTP/1.1 200 OK\r\n'
                'Content-Type: text/html\r\n'
                'Content-Length: 31\r\n'
                'Connection: Close\r\n\r\n'
                '<html>\r\n'
                'Hello world.\r\n'
                '</html>\r\n'
            )

        def on_data(self, data, all_data):
            Socket.on_data(self, data, all_data)
            if len(all_data) < 16:
                return all_data
            if all_data.startswith('GET / HTTP/1.1\r\n'):
                self.Send(self.response)
            self.Close()

    Loop.register(-1, EV_TIMEOUT, Loop.stop, 10)

    Server(server_addr, HttpClientHandler).Run()

if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '-c':
        test_client( (sys.argv[2], int(sys.argv[3])) )
    elif len(sys.argv) == 4 and sys.argv[1] == '-s':
        test_server( (sys.argv[2], int(sys.argv[3])) )

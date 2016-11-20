#!/env/bin/python
# -*- coding: utf-8 -*-

import socket
import sys

from eventloop import Loop, EV_READ, EV_WRITE, EV_ERROR
from logger import Logger

def Connect(server_addr):    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(0)
    sock.connect_ex(server_addr)
    return sock

# user defined methods' name convention:
#   Method -- public: callable, un-inheritable
#   method -- protected: un-callable, inheritable
#   _method -- private: un-callable, un-inheritable
# user defined attributes' name convention:
#   attribute -- readonly
#   _attribute -- hidden

class AsynSocket(Logger):
    def __init__(self, sock, addr, event_loop=None, tag=''):
        self.fd = sock.fileno()
        self.name = '%s<%s:%d>' % (self.__class__.__name__, addr[0], addr[1])
        self.name += tag and ('-'+tag)
        self.sock = sock
        self.event_loop = event_loop or Loop
        self.Run = self.event_loop.run
        self.read_buf = ''
        self.write_buf = []
        self.sock.setblocking(0)
        self.event_loop.register(self.fd, EV_READ, self._on_read)
        self.event_loop.register(self.fd, EV_WRITE, self._on_write)
        self.event_loop.register(self.fd, EV_ERROR, self._on_error)
        self.closed = False
        self.info('created')

    def _on_read(self):
        try:
            data = self.sock.recv(4096)
        except socket.error:
            self._on_error()
        else:
            if data:
                self.debug('recv', len(data), 'bytes')
                self.dump(data)
                self.read_buf = self.on_data(data, self.read_buf+data) or ''
            else:
                self._on_remote_close()

    def _on_write(self):
        if self.write_buf:
            data = ''.join(self.write_buf)
            try:
                n = self.sock.send(data)
            except socket.error:
                self._on_error()
            else:
                del self.write_buf[:]
                if n > 0:
                    sent, data = data[:n], data[n:]
                    self.debug('sent', n, 'bytes')
                    self.dump(sent)
                    self.on_sent(sent)
                if data:
                    self.write_buf.append(data)
                    return
        if self.closed:
            self._on_close()
    
    def _on_error(self):
        self.error('encountered error')
        self.on_error()
        self._destroy()
    
    def _on_remote_close(self):
        self.info('closed by remote')
        self.on_remote_close()
        self._destroy()
    
    def _on_close(self):        
        self.info('closed')
        self.on_close()
        self._destroy()

    def Close(self):
        self.closed = True
        if not self.write_buf:
            self._on_close()
        else:
            self.event_loop.unregister(self.fd, EV_READ)
    
    def Send(self, data):
        if not self.closed and data:
            self.write_buf.append(data)
    
    def _destroy(self):
        self.event_loop.unregister_all(self.fd)
        self.sock.close()
        self.on_destroy()
        
    def on_data(self, data, all_data):
        return all_data
    
    def on_sent(self, data):
        pass
    
    def on_error(self):
        pass
    
    def on_remote_close(self):
        pass
    
    def on_close(self):
        pass
    
    def on_destroy(self):
        pass

def test_client(server_addr):
    s = 'GET / HTTP/1.1\r\nHost: {0}\r\nConnection: Close\r\n\r\n'

    class HttpClient(AsynSocket):

        level = 'debug'

        def __init__(self, server_addr, i, event_loop=Loop):
            sock = Connect(server_addr)
            AsynSocket.__init__(self, sock, server_addr, event_loop, str(i))
            self.Send(s.format(server_addr[0]))

    for i in range(3):
        Loop.add_timeout(0, HttpClient, server_addr, i)

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
            self.notify('failed to start')
            self.on_failed_to_start(e)
        else:
            fd = self.sock.fileno()
            event_loop.register(fd, EV_READ, self._on_accept, event_loop)
            self.notify('started')
            self.on_start()

            try:
                event_loop.run()
            except KeyboardInterrupt:
                self.notify('abort')
                self.on_abort()
            except SystemExit:
                self.notify('stopped')
                self.on_stop()
            except Exception as e:
                self.notify('crashed', exc_info=True)
                self.on_crash(e)
            finally:
                event_loop.unregister(fd, EV_READ)
                self.sock.close()

    def Stop(self):
        raise SystemExit

    def _on_accept(self, event_loop):
        client_sock, client_addr = self.sock.accept()
        self.connection_handler(client_sock, client_addr, event_loop, self)  
    
    def on_failed_to_start(self, e):
        sys.exit(1)
    
    def on_start(self):
        pass
    
    def on_abort(self):
        sys.exit(1)    
    
    def on_stop(self):
        pass

    def on_crash(self, e):
        sys.exit(1)
    
    # used to replace `connection_handler` when it is not provided
    def handle(self, client_sock, client_addr, event_loop, server_obj):
        raise NotImplemented

def test_server(server_addr):

    class HttpClientHandler(AsynSocket):
        def __init__(self, sock, client_addr, event_loop, server_obj):
            AsynSocket.__init__(self, sock, client_addr, event_loop)
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
            if len(all_data) < 16:
                return all_data
            if all_data.startswith('GET / HTTP/1.1\r\n'):
                self.Send(self.response)
            self.Close()

    Server(server_addr, HttpClientHandler).Run()

if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '-c':
        test_client( (sys.argv[2], int(sys.argv[3])) )
    elif len(sys.argv) == 4 and sys.argv[1] == '-s':
        test_server( (sys.argv[2], int(sys.argv[3])) )

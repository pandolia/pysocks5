# -*- coding: utf-8 -*-

import sys
import struct
import socket

from sockserver import AsynSocket, Server, Connect

import config

def start_proxy():
    TunnelServer((config.tunnel_ip, config.tunnel_port)).Run()
    ProxyServer(('0.0.0.0', config.proxy_port)).Run()

class TunnelServer(Server):
    def __init__(self, addr):
        Server.__init__(self, addr, num_listens=1)
        
    def handle(self, client_sock, client_addr, event_loop, server_obj):
        TunnelServer.tunnel = LTunnel(client_sock, client_addr, event_loop)
        self.Stop()

class ProxyServer(Server):
    def handle(self, clt_sock, clt_addr, event_loop, server_obj):
        TunnelServer.tunnel.AddSrc(clt_sock, clt_addr, clt_sock.fileno())

class LTunnel(AsynSocket):

    level = 'info'

    def __init__(self, sock, addr, event_loop):
        AsynSocket.__init__(self, sock, addr, event_loop)
        self.src_map = {}
    
    def on_data(self, data, all_data):
        while True:
            try:
                pkg_id, pkg_data, all_data = unpack(all_data)
            except struct.error:
                return all_data
            else:
                self.send_to_src(pkg_id, pkg_data)
    
    def on_destroy(self):
        sys.exit(1)

    def send_to_src(self, src_id, data):
        try:
            src = self.src_map[src_id]
        except KeyError:
            pass
        else:
            if data:
                src.Send(data)
            else:
                src.Close()

    def AddSrc(self, src_sock, src_addr, src_id):
        self.src_map[src_id] = \
            SrcSocket(src_sock, src_addr, src_id, self.event_loop, self)
    
    def DelSrc(self, src_id, notify=True):
        self.src_map.pop(src_id, None)
        if notify:
            self.Send(src_id, '')
    
    def Send(self, src_id, data):
        AsynSocket.Send(self, pack(src_id, data))
    
class SrcSocket(AsynSocket):

    level = config.log_level

    def __init__(self, sock, addr, _id, event_loop, tunnel):
        AsynSocket.__init__(self, sock, addr, event_loop, str(_id))
        self.id = _id
        self.tunnel = tunnel
    
    def on_data(self, data, all_data):
        self.tunnel.Send(self.id, data)
    
    def on_destroy(self):
        self.tunnel.DelSrc(self.id, notify=(not self.closed))

def start_backdoor():
    addr = config.tunnel_ip, config.tunnel_port
    RTunnel(Connect(addr), addr, None).Run()

class UnformedSrc:
    def __init__(self, stage, cmd_buf):
        self.stage, self.cmd_buf = stage, cmd_buf

class RTunnel(LTunnel):
    def send_to_src(self, src_id, data):
        src = self.src_map.get(src_id, None)
        if isinstance(src, SrcSocket):
            if data:
                src.Send(data)
            else:
                src.Close()
            return
            
        if src is None:
            src = UnformedSrc(stage=0, cmd_buf=data)
            self.src_map[src_id] = src
        else:
            src.cmd_buf += data
        
        (src.stage and self._stage1 or self._stage0)(src_id, src)

    def _stage0(self, src_id, src):
        cmd_buf = src.cmd_buf
        
        if len(cmd_buf) < 3:
            return
        
        n_methods = ord(cmd_buf[1])
        
        if (len(cmd_buf) - 2) < n_methods:
            return
        
        ver, methods = ord(cmd_buf[0]), cmd_buf[2:2+n_methods]
        
        if ver != 0x05 or '\x00' not in methods:
            self.Send(src_id, '\x05\xff')
            self.DelSrc(src_id)
            return
       
        self.Send(src_id, '\x05\x00')
        src.stage = 1
        src.cmd_buf = cmd_buf[2+n_methods:]

        if src.cmd_buf:
            self._stage1(src_id, src)
    
    def _stage1(self, src_id, src):
        cmd_buf = src.cmd_buf
        
        if len(cmd_buf) < 7:
            return
        
        ver, cmd, rsv, atyp = map(ord, cmd_buf[:4])
        
        if ver != 0x05 or cmd != 0x01 or atyp not in (0x01, 0x03):
            self.DelSrc(src_id)
            return
        
        if atyp == 0x01:
            if len(cmd_buf) < 10:
                return
            i = 8
            host = socket.inet_ntoa(cmd_buf[4:i])
        else:
            len_host = ord(cmd_buf[4])
            if len(cmd_buf) < len_host + 7:
                return
            i = len_host + 5
            host = cmd_buf[5:i]
        
        port = struct.unpack('>H', cmd_buf[i:i+2])[0]
        addr = host, port
        cmd_buf = cmd_buf[i+2:]
        
        reply = socket.inet_aton('0.0.0.0')
        reply += struct.pack(">H", config.proxy_port)
        
        try:
            sock = Connect(addr)
        except socket.error:
            self.Send(src_id, '\x05\x04\x00\x01'+reply)
            self.DelSrc(src_id)
            return
        
        self.Send(src_id, '\x05\x00\x00\x01'+reply)
        src = SrcSocket(sock, addr, src_id, self.event_loop, self)
        self.src_map[src_id] = src
        
        if cmd_buf:
            src.Send(cmd_buf)

def pack(pkg_id, pkg_data):
    return struct.pack('>HI', len(pkg_data), pkg_id) + pkg_data

def unpack(pkg):
    pkg_len, pkg_id = struct.unpack('>HI', pkg[:6])
    if len(pkg) < (6 + pkg_len):
        raise struct.error
    pkg_data, remain = pkg[6:6+pkg_len], pkg[6+pkg_len:]
    return pkg_id, pkg_data, remain

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] in ('-p', '--start-proxy'):
        start_proxy()
    elif len(sys.argv) == 2 and sys.argv[1] in ('-b', '--start-backdoor'):
        start_backdoor()


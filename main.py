import socket
import threading
import hashlib
import base64
import struct
import select
import json
import time
import sys

# ======================
# webSocket Protocol Implementation
# ======================

class WebSocketFrame:
    """will be handling RFC 6544
    v.0.1 - text, binary, close, ping
    """
    OPCODE_CONT = 0x0
    OPCODE_TEXT = 0x1
    OPCODE_BINARY = 0x2
    OPCODE_CLOSE = 0x8
    OPCODE_PING = 0x9
    OPCODE_PONG = 0xA

    @staticmethod
    def create_frame(payload, opcode=OPCODE_TEXT, mask=True):
        """
        creating a WebSocket frame
        - FIN bit set (1)
        - RSV bits cleared (0)
        - Payload masked for client-to-server
        """
        frame = bytearray()
        # FIN (1), RSV1-3 (0), opcode (4 bits)
        frame.append(0x80 | opcode)
        payload_len = len(payload)
        if payload_len <= 125:
            frame.append(0x80 | payload_len)  
        elif payload_len <= 65535:
            frame.append(0x80 | 126)
            frame.extend(struct.pack(">H", payload_len))
        else:
            frame.append(0x80 | 127)
            frame.extend(struct.pack(">Q", payload_len))
        
        masking_key = struct.pack(">I", int(time.time() * 1000) % 0xFFFFFFFF)
        frame.extend(masking_key)
        masked_payload = bytearray()
        for i, byte in enumerate(payload):
            masked_payload.append(byte ^ masking_key[i % 4])
        frame.extend(masked_payload)
        
        return bytes(frame)

    @staticmethod
    def parse_frame(data):
        """Parse WebSocket frame and return (opcode, payload, payload_length, fin)"""
        if len(data) < 2:
            return None, None, 0, False, 0
        
        byte1 = data[0]
        fin = (byte1 & 0x80) != 0
        opcode = byte1 & 0x0F
        byte2 = data[1]
        mask = (byte2 & 0x80) != 0
        payload_len = byte2 & 0x7F
        header_size = 2
        if payload_len == 126:
            if len(data) < 4:
                return None, None, 0, False, 0
            payload_len = struct.unpack(">H", data[2:4])[0]
            header_size += 2
        elif payload_len == 127:
            if len(data) < 10:
                return None, None, 0, False, 0
            payload_len = struct.unpack(">Q", data[2:10])[0]
            header_size += 8
        if mask:
            header_size += 4
            masking_key = data[header_size-4:header_size]
        if len(data) < header_size + payload_len:
            return None, None, 0, False, 0
        payload = data[header_size:header_size+payload_len]
        if mask:
            payload = bytearray(payload)
            for i in range(payload_len):
                payload[i] ^= masking_key[i % 4]
        
        return opcode, bytes(payload), payload_len, fin, header_size + payload_len

# ======================
# WebSocket Server
# ======================

class WebSocketServer:
    """WebSocket server implementing RFC 6455 handshake and frame handling"""
    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    
    def __init__(self, host='127.0.0.1', port=8000):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}
        self.running = False
    
    def _handshake(self, client_sock):
        data = client_sock.recv(4096).decode('utf-8')
        if not data.startswith('GET'):
            return False
        
        headers = {}
        for line in data.split('\r\n')[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key.lower()] = val
        
        if ('upgrade' not in headers or 'websocket' not in headers['upgrade'].lower() or
            'connection' not in headers or 'upgrade' not in headers['connection'].lower() or
            'sec-websocket-key' not in headers):
            return False
        
        key = headers['sec-websocket-key'] + self.GUID
        accept_key = base64.b64encode(hashlib.sha1(key.encode()).digest()).decode()
        
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        )
        client_sock.send(response.encode())
        return True
    
    def _handle_client(self, client_sock, addr):
        """Handle client connection after handshake"""
        try:
            while self.running:
                ready = select.select([client_sock], [], [], 1)
                if not ready[0]:
                    continue
                
                data = client_sock.recv(4096)
                if not data:
                    break
                
                buffer = data
                while buffer:
                    opcode, payload, plen, fin, frame_len = WebSocketFrame.parse_frame(buffer)
                    if opcode is None:  # Incomplete frame
                        break
                    
                    if opcode == WebSocketFrame.OPCODE_TEXT:
                        message = payload.decode('utf-8')
                        self.broadcast(message, client_sock)
                    elif opcode == WebSocketFrame.OPCODE_CLOSE:
                        self.close_client(client_sock)
                        return
                    elif opcode == WebSocketFrame.OPCODE_PING:
                        pong_frame = WebSocketFrame.create_frame(b'', opcode=WebSocketFrame.OPCODE_PONG)
                        client_sock.send(pong_frame)
                    
                    buffer = buffer[frame_len:]
        except (ConnectionResetError, OSError):
            pass
        finally:
            self.close_client(client_sock)
    
    def broadcast(self, message, sender_sock=None):
        """Send message to all connected clients"""
        frame = WebSocketFrame.create_frame(message.encode('utf-8'))
        for sock in list(self.clients.keys()):
            if sock != sender_sock:
                try:
                    sock.send(frame)
                except (OSError, ConnectionResetError):
                    self.close_client(sock)
    
    def close_client(self, client_sock):
        """Close client connection gracefully"""
        if client_sock in self.clients:
            username = self.clients.pop(client_sock)
            close_frame = WebSocketFrame.create_frame(b'', opcode=WebSocketFrame.OPCODE_CLOSE)
            try:
                client_sock.send(close_frame)
                client_sock.close()
            except OSError:
                pass
            self.broadcast(f"{username} has left the chat")
    
    def start(self):
        """Start the WebSocket server"""
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True
        print(f"WebSocket server listening on {self.host}:{self.port}")
        
        while self.running:
            try:
                client_sock, addr = self.sock.accept()
                if self._handshake(client_sock):
                    # Get username from first message
                    data = client_sock.recv(4096)
                    opcode, payload, _, _, _ = WebSocketFrame.parse_frame(data)
                    if opcode == WebSocketFrame.OPCODE_TEXT:
                        username = payload.decode('utf-8')
                        self.clients[client_sock] = username
                        self.broadcast(f"{username} joined the chat")
                        threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True).start()
            except OSError:
                break
    
    def stop(self):
        """Stop the server gracefully"""
        self.running = False
        for sock in list(self.clients.keys()):
            self.close_client(sock)
        self.sock.close()

# ======================
# WebSocket Client
# ======================

class WebSocketClient:
    """WebSocket client implementing RFC 6455 protocol"""
    
    def __init__(self, host='127.0.0.1', port=8000):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False
    
    def connect(self, username):
        """Establish WebSocket connection with username"""
        try:
            self.sock.connect((self.host, self.port))
            self._handshake()
            self.connected = True
            self.send(username)  # Send username as first message
            return True
        except (ConnectionRefusedError, OSError) as e:
            print(f"Connection failed: {e}")
            return False
    
    def _handshake(self):
        """Perform WebSocket handshake"""
        key = base64.b64encode(hashlib.sha1(str(time.time()).encode()).digest()[:16]).decode()
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.send(request.encode())
        
        # Verify response
        response = self.sock.recv(4096).decode('utf-8')
        if "101 Switching Protocols" not in response:
            raise ConnectionError("Invalid handshake response")
    
    def send(self, message):
        """Send text message to server"""
        frame = WebSocketFrame.create_frame(message.encode('utf-8'))
        self.sock.send(frame)
    
    def receive(self):
        """Receive and decode messages from server"""
        buffer = b''
        while self.connected:
            try:
                ready = select.select([self.sock], [], [], 0.1)
                if ready[0]:
                    data = self.sock.recv(4096)
                    if not data:
                        self.close()
                        return None
                    buffer += data
                    
                    while buffer:
                        opcode, payload, plen, fin, frame_len = WebSocketFrame.parse_frame(buffer)
                        if opcode is None:  # incomplete frame
                            break
                        
                        buffer = buffer[frame_len:]
                        if opcode == WebSocketFrame.OPCODE_TEXT:
                            return payload.decode('utf-8')
                        elif opcode == WebSocketFrame.OPCODE_CLOSE:
                            self.close()
                            return None
            except (ConnectionResetError, OSError):
                self.close()
                return None
        return None
    
    def close(self):
        """Close connection gracefully"""
        if self.connected:
            try:
                close_frame = WebSocketFrame.create_frame(b'', opcode=WebSocketFrame.OPCODE_CLOSE)
                self.sock.send(close_frame)
            except OSError:
                pass
            self.sock.close()
            self.connected = False

# ======================
# Chat Application
# ======================

def run_chat_server():
    """Run WebSocket chat server"""
    server = WebSocketServer()
    server_thread = threading.Thread(target=server.start)
    server_thread.daemon = True
    server_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("\nServer stopped")

def run_chat_client(username):
    """Run WebSocket chat client"""
    client = WebSocketClient()
    if not client.connect(username):
        return
    
    # Message receiver thread
    def receive_messages():
        while client.connected:
            message = client.receive()
            if message:
                print(f"\r{message}\n> ", end='')
    
    threading.Thread(target=receive_messages, daemon=True).start()
    
    try:
        while client.connected:
            message = input("> ")
            if message.lower() == '/exit':
                client.close()
                break
            if client.connected:
                client.send(message)
    except KeyboardInterrupt:
        client.close()
    print("Disconnected")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        run_chat_server()
    elif len(sys.argv) > 2 and sys.argv[1] == "client":
        run_chat_client(sys.argv[2])
    else:
        print("Usage:")
        print("  python websocket_chat.py server")
        print("  python websocket_chat.py client <username>")
#!/usr/bin/env python3
import socket
import threading
import select

LISTEN_PORT = 8443
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 40000
TARGET_HOST = "generativelanguage.googleapis.com"
TARGET_PORT = 443

def handle_client(client_socket):
    proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        proxy_socket.connect((PROXY_HOST, PROXY_PORT))
        
        # Send HTTP CONNECT
        connect_req = f"CONNECT {TARGET_HOST}:{TARGET_PORT} HTTP/1.1\r\nHost: {TARGET_HOST}:{TARGET_PORT}\r\n\r\n"
        proxy_socket.sendall(connect_req.encode())
        
        # Read HTTP Response header (basic implementation)
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = proxy_socket.recv(4096)
            if not chunk:
                client_socket.close()
                return
            response += chunk
            
        header, body_start = response.split(b"\r\n\r\n", 1)
        if b"200 Connection established" not in header and b"200 OK" not in header:
            print(f"Proxy refused connection: {header}")
            client_socket.close()
            return

        # If we have body data from handshake (unlikely for CONNECT but possible), send it
        if body_start:
            client_socket.sendall(body_start)

        # Pipe data
        inputs = [client_socket, proxy_socket]
        while True:
            readable, _, _ = select.select(inputs, [], [])
            for s in readable:
                other = proxy_socket if s is client_socket else client_socket
                try:
                    data = s.recv(16384)
                    if not data:
                        return
                    other.sendall(data)
                except Exception:
                    return

    except Exception as e:
        print(f"Error handling connection: {e}")
    finally:
        client_socket.close()
        proxy_socket.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', LISTEN_PORT))
    server.listen(10)
    print(f"Gemini Proxy listening on {LISTEN_PORT} -> WARP {PROXY_HOST}:{PROXY_PORT}")

    while True:
        try:
            client, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client,))
            t.daemon = True
            t.start()
        except Exception as e:
            print(f"Accept error: {e}")

if __name__ == "__main__":
    main()

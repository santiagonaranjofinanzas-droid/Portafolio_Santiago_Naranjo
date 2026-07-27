import socket
import sys

def test_port(port):
    print(f"Connecting to port {port}...")
    try:
        s = socket.socket()
        s.settimeout(60.0)
        s.connect(('127.0.0.1', port))
        s.sendall(b'GET_WEIGHTS\n')
        
        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
            if b'\n' in chunk:
                break
                
        response = res.decode('utf-8')
        if response.startswith("ERROR"):
            print(f"Server returned error: {response}")
        else:
            print("Successfully received weights!")
            print("Response preview:", response[:150] + "...")
    except Exception as e:
        print(f"Failed to connect or retrieve weights on port {port}: {e}")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    test_port(port)

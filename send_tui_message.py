import socket
import sys

def send_message(host='localhost', port=9000, message='Hello TUI'):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            if not message.endswith('\n'):
                message += '\n'
            s.sendall(message.encode('utf-8'))
            print(f"Sent: {message.strip()}")
    except ConnectionRefusedError:
        print(f"Error: Could not connect to {host}:{port}. Is the TUI running?")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello from Python Client"
    send_message(message=msg)


import socket, threading, json, sys

SERVER_IP = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = 5000

def receive(sock):
    f = sock.makefile("r", encoding="utf-8")
    for line in f:
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        tag = {"private": "[PM] ", "error": "[!] ", "info": "[i] "}.get(m["type"], "")
        print(f"\r{tag}{m['from']}: {m['text']}" if m["type"] in ("chat", "private")
              else f"\r{tag}{m['text']}")
    print("Disconnected from server.")
    sys.exit(0)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, PORT))
    threading.Thread(target=receive, args=(sock,), daemon=True).start()
    try:
        while True:
            msg = input()
            sock.sendall((msg + "\n").encode())
            if msg == "/quit":
                break
    except (KeyboardInterrupt, EOFError):
        sock.sendall(b"/quit\n")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
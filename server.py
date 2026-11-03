import socket, threading, json, datetime

HOST, PORT = "0.0.0.0", 5000
MAX_B64 = 7_000_000            # ~5 MB file limit after base64 encoding
clients = {}                   # username -> socket
lock = threading.Lock()


def log(text):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {text}"
    print(line)
    with open("chat_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def send(sock, msg_type, text, sender="SERVER", extra=None):
    payload = {"type": msg_type, "from": sender, "text": text}
    if extra:
        payload.update(extra)
    try:
        sock.sendall((json.dumps(payload) + "\n").encode())
    except OSError:
        pass


def broadcast(text, sender, exclude=None):
    with lock:
        for name, s in list(clients.items()):
            if name != exclude:
                send(s, "chat", text, sender)


def handle_client(conn, addr):
    f = conn.makefile("r", encoding="utf-8")
    username = None
    try:
        send(conn, "info", "Enter your username:")
        username = f.readline().strip()
        with lock:
            if not username or username in clients:
                send(conn, "error", "Invalid or duplicate username.")
                username = None
                conn.close()
                return
            clients[username] = conn
        log(f"{username} joined from {addr}")
        broadcast(f"{username} joined the chat.", "SERVER")
        send(conn, "info", "Commands: /list, /msg <user> <text>, /file <name> <base64>, /quit")

        for line in f:
            line = line.strip()
            if not line:
                continue

            if line == "/quit":
                break

            elif line == "/list":
                with lock:
                    users = ", ".join(clients)
                send(conn, "info", f"Online: {users}")

            elif line.startswith("/file "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    send(conn, "error", "Usage: /file <name> <base64>")
                    continue
                _, fname, b64 = parts
                if len(b64) > MAX_B64:
                    send(conn, "error", "File too large (max 5 MB).")
                    continue
                log(f"FILE {username} shared {fname} ({len(b64) * 3 // 4} bytes)")
                with lock:
                    for name, s in list(clients.items()):
                        if name != username:
                            send(s, "file", fname, username, {"data": b64})
                send(conn, "info", f"File '{fname}' sent.")

            elif line.startswith("/msg "):
                parts = line.split(" ", 2)
                if len(parts) < 3:
                    send(conn, "error", "Usage: /msg <user> <text>")
                    continue
                _, target, text = parts
                with lock:
                    t = clients.get(target)
                if t:
                    send(t, "private", text, username)
                    send(conn, "info", f"(private to {target}) {text}")
                    log(f"PRIVATE {username}->{target}: {text}")
                else:
                    send(conn, "error", f"User '{target}' not found.")

            else:
                log(f"{username}: {line}")
                broadcast(line, username, exclude=username)

    except (ConnectionResetError, OSError):
        pass
    finally:
        if username:
            with lock:
                clients.pop(username, None)
            broadcast(f"{username} left the chat.", "SERVER")
            log(f"{username} disconnected")
        try:
            conn.close()
        except OSError:
            pass


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen()
    log(f"Server listening on {HOST}:{PORT}")
    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        log("Server shutting down")
    finally:
        srv.close()


if __name__ == "__main__":
    main()
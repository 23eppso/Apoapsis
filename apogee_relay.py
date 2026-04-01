import socket, threading, time, random, string

RELAY_PORT = 7779
ROOM_TTL   = 300   # seconds before a room expires (5 minutes)

rooms = {}   # code → {ip, port, expires}
lock  = threading.Lock()

def random_code():
    chars = string.ascii_uppercase.replace("O","").replace("I","")   # no confusing chars
    return "".join(random.choices(chars, k=4))

def fresh_code():
    with lock:
        for _ in range(100):
            code = random_code()
            if code not in rooms:
                return code
    return None

def expire_rooms():
    while True:
        time.sleep(30)
        now = time.time()
        with lock:
            expired = [c for c, r in rooms.items() if r["expires"] < now]
            for c in expired:
                del rooms[c]
                print(f"[relay] room {c} expired")

def handle(conn, addr):
    try:
        data = conn.recv(256).decode().strip()
        parts = data.split()
        if not parts:
            conn.sendall(b"ERROR empty\n"); return

        cmd = parts[0].upper()

        if cmd == "PING":
            conn.sendall(b"PONG\n")

        elif cmd == "REGISTER" and len(parts) == 3:
            ip, port = parts[1], parts[2]
            code = fresh_code()
            if code is None:
                conn.sendall(b"ERROR no_codes\n"); return
            with lock:
                rooms[code] = {"ip": ip, "port": port, "expires": time.time() + ROOM_TTL}
            print(f"[relay] registered {code} → {ip}:{port}")
            conn.sendall(f"OK {code}\n".encode())

        elif cmd == "LOOKUP" and len(parts) == 2:
            code = parts[1].upper()
            with lock:
                room = rooms.get(code)
            if room and room["expires"] > time.time():
                conn.sendall(f"IP {room['ip']} {room['port']}\n".encode())
            else:
                conn.sendall(b"NOTFOUND\n")

        elif cmd == "CLOSE" and len(parts) == 2:
            code = parts[1].upper()
            with lock:
                rooms.pop(code, None)
            print(f"[relay] closed {code}")
            conn.sendall(b"OK\n")

        else:
            conn.sendall(b"ERROR unknown_command\n")

    except Exception as e:
        print(f"[relay] error from {addr}: {e}")
    finally:
        conn.close()

def main():
    threading.Thread(target=expire_rooms, daemon=True).start()
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", RELAY_PORT))
    srv.listen(32)
    print(f"[relay] listening on :{RELAY_PORT}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()


import socket, threading, time, random, string, os
from http.server import HTTPServer, BaseHTTPRequestHandler

RELAY_PORT = 7779
ROOM_TTL   = 300

rooms = {}
lock  = threading.Lock()

def random_code():
    chars = string.ascii_uppercase.replace("O","").replace("I","")
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
        data  = conn.recv(256).decode().strip()
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
            print(f"[relay] registered {code} -> {ip}:{port}")
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
            conn.sendall(b"OK\n")
        else:
            conn.sendall(b"ERROR unknown\n")
    except Exception as e:
        print(f"[relay] error from {addr}: {e}")
    finally:
        conn.close()

def run_relay():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", RELAY_PORT))
    srv.listen(32)
    print(f"[relay] TCP relay listening on :{RELAY_PORT}")
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"APOGEE relay running")
    def log_message(self, *args): pass

def run_http():
    port = int(os.environ.get("PORT", 10000))
    print(f"[relay] HTTP health check on :{port}")
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=expire_rooms, daemon=True).start()
    threading.Thread(target=run_relay,    daemon=True).start()
    run_http()

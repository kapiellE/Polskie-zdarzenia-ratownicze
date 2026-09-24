#!/usr/bin/env python3
"""Serwer multiplayer dla aplikacji 112. Sama biblioteka standardowa - nic nie trzeba instalowac.
Start:  python3 server.py      (port z zmiennej PORT, domyslnie 8080)"""
import json, os, re, secrets, threading, time, hashlib, hmac
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
DBFILE = os.path.join(BASE, "data.json")
ADMIN, ADMIN_PW = "kapiello", "XBGTfemboy"
LOCK = threading.Lock()
SEEN = {}  # nick(lower) -> ostatnia aktywnosc (w pamieci)
NICK = re.compile(r"^[\w.-]{3,10}$")

def load():
    try:
        with open(DBFILE, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {"users": {}, "tokens": {}, "banned": [], "devs": {}, "events": [], "ann": [], "chat": []}

def save(d):
    tmp = DBFILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(d, f)
    os.replace(tmp, DBFILE)

def hpw(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 60000).hex()
def nid(): return secrets.token_hex(5)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    def out(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.cors()
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()
    def who(self, d):
        t = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        return d["tokens"].get(t)
    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/api/"): return self.api("GET", u, None)
        f = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"),
             "/logo.png": ("logo.png", "image/png")}.get(u.path)
        if not f: return self.out(404, {"error": "not_found"})
        try:
            with open(os.path.join(BASE, f[0]), "rb") as fh: b = fh.read()
        except Exception: return self.out(404, {"error": "not_found"})
        self.send_response(200); self.send_header("Content-Type", f[1]); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_500_000: return self.out(413, {"error": "too_big"})
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except Exception: return self.out(400, {"error": "bad_json"})
        self.api("POST", urlparse(self.path), body)
    def api(self, method, u, b):
        with LOCK:
            d = load()
            try: code, res = self.route(method, u, b, d)
            except Exception as e: code, res = 500, {"error": "server"}
            if code == 200 and method == "POST": save(d)
        self.out(code, res)
    def route(self, method, u, b, d):
        p = u.path
        if p in ("/api/login", "/api/register") and method == "POST":
            nick = str(b.get("nick", "")).strip(); pw = str(b.get("pw", "")); k = nick.lower()
            if not NICK.match(nick) or len(pw) < 4: return 400, {"error": "invalid"}
            if k in d["banned"]: return 403, {"error": "banned"}
            if p == "/api/register":
                dev = str(b.get("dev", ""))[:40] or "x"
                if k in d["users"]: return 409, {"error": "taken"}
                if k == ADMIN and pw != ADMIN_PW: return 401, {"error": "bad_credentials"}
                if d["devs"].get(dev, 0) >= 3: return 429, {"error": "limit"}
                s = secrets.token_hex(8); d["users"][k] = {"nick": nick, "salt": s, "h": hpw(pw, s), "ts": int(time.time() * 1000)}
                d["devs"][dev] = d["devs"].get(dev, 0) + 1
            else:
                usr = d["users"].get(k)
                if not usr or not hmac.compare_digest(usr["h"], hpw(pw, usr["salt"])): return 401, {"error": "bad_credentials"}
                nick = usr["nick"]
            t = secrets.token_hex(24); d["tokens"][t] = d["users"][k]["nick"]
            return 200, {"token": t, "nick": d["users"][k]["nick"], "admin": k == ADMIN}
        me = self.who(d)
        if not me: return 401, {"error": "auth"}
        k = me.lower(); adm = k == ADMIN
        if k in d["banned"]: return 403, {"error": "banned"}
        SEEN[k] = time.time()
        if p == "/api/me": return 200, {"nick": me, "admin": adm}
        if p == "/api/list":
            col = parse_qs(u.query).get("col", [""])[0]
            if col not in ("events", "ann", "chat"): return 400, {"error": "col"}
            it = d[col]
            return 200, {"items": it[-100:] if col == "chat" else it[::-1][:50]}
        if method != "POST": return 404, {"error": "nf"}
        if p == "/api/post":
            col = b.get("col"); text = str(b.get("text", "")).strip()
            img = b.get("img") if isinstance(b.get("img"), str) and len(b.get("img", "")) < 900_000 and b["img"].startswith("data:image/") else None
            if col == "chat":
                m = re.match(r"^/(ban|unban|kick|kik|users)(?:\s+(\S+))?\s*$", text, re.I)
                if m:
                    if not adm: return 403, {"error": "forbidden"}
                    cmd, arg = m.group(1).lower(), (m.group(2) or "")
                    ts = int(time.time() * 1000)
                    def sysmsg(t): d["chat"].append({"id": nid(), "nick": "System", "text": t, "ts": ts})
                    if cmd == "users":
                        rows = []
                        for kk, u2 in sorted(d["users"].items(), key=lambda x: x[1].get("ts", 0)):
                            on = time.time() - SEEN.get(kk, 0) < 15
                            j = time.strftime("%d.%m.%Y", time.localtime(u2["ts"] / 1000)) if u2.get("ts") else "?"
                            rows.append(("🟢 " if on else "⚪ ") + u2["nick"] + " (od " + j + ")" + (" 🚫 ban" if kk in d["banned"] else ""))
                        return 200, {"reply": "Użytkownicy (" + str(len(rows)) + "):\n" + "\n".join(rows)}
                    if not arg: return 200, {"reply": "Użycie: /" + cmd + " nick"}
                    t = arg.lower()
                    if t == ADMIN: return 200, {"reply": "Nie możesz tego zrobić na adminie."}
                    if t not in d["users"]: return 200, {"reply": "Nie ma takiego konta: " + arg}
                    if cmd == "ban":
                        if t not in d["banned"]: d["banned"].append(t)
                        d["tokens"] = {a: n for a, n in d["tokens"].items() if n.lower() != t}
                        sysmsg(d["users"][t]["nick"] + " dostał bana.")
                    elif cmd == "unban":
                        d["banned"] = [x for x in d["banned"] if x != t]; sysmsg(d["users"][t]["nick"] + " został odbanowany.")
                    else:
                        d["tokens"] = {a: n for a, n in d["tokens"].items() if n.lower() != t}
                        sysmsg(d["users"][t]["nick"] + " został wyrzucony (kick).")
                    return 200, {"ok": True}
                if not text or len(text) > 500: return 400, {"error": "text"}
                d["chat"].append({"id": nid(), "nick": me, "text": text, "ts": int(time.time() * 1000)})
                d["chat"] = d["chat"][-300:]; return 200, {"ok": True}
            if col in ("events", "ann"):
                if not adm: return 403, {"error": "forbidden"}
                if not text and not img: return 400, {"error": "text"}
                it = {"id": nid(), "nick": me, "text": text[:2000], "ts": int(time.time() * 1000)}
                if img: it["img"] = img
                a1, a2 = str(b.get("a1") or "").strip()[:60], str(b.get("a2") or "").strip()[:60]
                if col == "ann" and a1 and a2: it.update(a1=a1, a2=a2, v1=[], v2=[])
                d[col].append(it); return 200, {"ok": True}
            return 400, {"error": "col"}
        if p == "/api/vote":
            for it in d["ann"]:
                if it["id"] == b.get("id") and "a1" in it:
                    if me in it["v1"] or me in it["v2"]: return 200, {"ok": True}
                    it["v1" if b.get("i") == 1 else "v2"].append(me); return 200, {"ok": True}
            return 404, {"error": "nf"}
        if p == "/api/delete":
            if not adm: return 403, {"error": "forbidden"}
            col = b.get("col")
            if col in ("events", "ann", "chat"): d[col] = [x for x in d[col] if x["id"] != b.get("id")]
            return 200, {"ok": True}
        return 404, {"error": "nf"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT") or os.environ.get("SERVER_PORT") or 8080)
    print("Serwer 112 działa na porcie", port)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()

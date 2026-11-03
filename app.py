import streamlit as st, socket, threading, json, base64, time, re, html

st.set_page_config(page_title="Distributed Chat", page_icon="💬", layout="centered")

st.markdown("""
<style>
.row{display:flex;margin:6px 0}
.row.me{justify-content:flex-end}
.bubble{max-width:72%;padding:8px 13px;border-radius:16px;line-height:1.35;
        font-size:15px;word-wrap:break-word}
.mine{background:#0b84f3;color:#fff;border-bottom-right-radius:4px}
.other{background:#2d313c;color:#eee;border-bottom-left-radius:4px}
.priv{background:#7b3fe4;color:#fff}
.file{background:#1f6f50;color:#fff}
.name{font-size:12px;font-weight:600;opacity:.85;margin-bottom:2px}
.meta{font-size:10px;opacity:.65;text-align:right;margin-top:3px}
.sys{text-align:center;color:#8b8f99;font-size:12px;margin:8px 0}
.err{text-align:center;color:#ff6b6b;font-size:12px;margin:8px 0}
.dot{color:#2ecc71}
</style>
""", unsafe_allow_html=True)

SKIP = ("Enter your username:", "Commands:")

class Conn:
    def __init__(self, host, port, user):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.settimeout(None)
        self.messages, self.online, self.alive = [], [], True
        self.last_poll = 0
        threading.Thread(target=self._rx, daemon=True).start()
        time.sleep(0.3)
        self.sock.sendall((user + "\n").encode())

    def _rx(self):
        try:
            for line in self.sock.makefile("r", encoding="utf-8"):
                m = json.loads(line)
                m["ts"] = time.time()
                t, txt = m["type"], m["text"]
                if t == "info" and txt.startswith("Online:"):
                    self.online = [u.strip() for u in txt[7:].split(",")]
                    continue
                if t == "info" and txt.startswith(SKIP):
                    continue
                p = re.match(r"\(private to (\S+)\) (.*)", txt, re.S)
                if t == "info" and p:
                    m.update(type="myprivate", to=p.group(1), text=p.group(2))
                self.messages.append(m)
        except Exception:
            pass
        self.alive = False

    def send(self, text):
        self.sock.sendall((text + "\n").encode())

    def echo(self, **kw):
        self.messages.append({"ts": time.time(), "from": "You", **kw})

    def close(self):
        try:
            self.send("/quit"); self.sock.close()
        except OSError:
            pass

def esc(t): return html.escape(t).replace("\n", "<br>")
def hm(ts): return time.strftime("%H:%M", time.localtime(ts))

def bubble(text, ts, cls, mine=False, name=None):
    n = f'<div class="name">{esc(name)}</div>' if name else ""
    st.markdown(
        f'<div class="row {"me" if mine else ""}"><div class="bubble {cls}">'
        f'{n}{esc(text)}<div class="meta">{hm(ts)}</div></div></div>',
        unsafe_allow_html=True)

def sysline(text, cls="sys"):
    st.markdown(f'<div class="{cls}">{esc(text)}</div>', unsafe_allow_html=True)

# ---------------- Login ----------------
if "conn" not in st.session_state:
    st.title("💬 Distributed Chat")
    host = st.text_input("Server IP", "127.0.0.1")
    port = st.number_input("Port", value=5000, step=1)
    user = st.text_input("Username")
    if st.button("Connect", type="primary") and user.strip():
        try:
            c = Conn(host, int(port), user.strip())
            time.sleep(0.7)
            errs = [m for m in c.messages if m["type"] == "error"]
            if errs:
                st.error(errs[0]["text"])
            else:
                st.session_state.conn, st.session_state.user = c, user.strip()
                st.rerun()
        except OSError as e:
            st.error(f"Could not connect: {e}")
    st.stop()

conn, user = st.session_state.conn, st.session_state.user

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header(f"👤 {user}")
    last_n = st.slider("Messages shown", 10, 200, 50, step=10)

    @st.fragment(run_every=2)
    def online_panel():
        if time.time() - conn.last_poll > 5 and conn.alive:
            conn.send("/list"); conn.last_poll = time.time()
        st.subheader(f"🟢 Online ({len(conn.online)})")
        for u in conn.online:
            st.markdown(f'<span class="dot">●</span> {esc(u)}'
                        f'{" (you)" if u == user else ""}', unsafe_allow_html=True)
    online_panel()

    st.divider()
    st.subheader("📎 Share a file")
    up = st.file_uploader("Max 5 MB", key="uploader", label_visibility="collapsed")
    if st.button("Send file", use_container_width=True) and up is not None:
        if up.size > 5 * 1024 * 1024:
            st.error("File too large.")
        else:
            safe = re.sub(r"\s+", "_", up.name)
            conn.send(f"/file {safe} {base64.b64encode(up.getvalue()).decode()}")
            conn.echo(type="myfile", text=safe, size=up.size)
            st.success(f"Sent {safe}")
    st.divider()
    if st.button("Disconnect", use_container_width=True):
        conn.close(); del st.session_state["conn"]; st.rerun()

# ---------------- Tabs ----------------
st.title("💬 Chat Room")
tab_pub, tab_priv, tab_files = st.tabs(["🌐 Public", "🔒 Private", "📁 Files"])

with tab_pub:
    @st.fragment(run_every=1)
    def public_view():
        if not conn.alive:
            sysline("Disconnected from server.", "err")
        for m in list(conn.messages)[-last_n:]:
            t = m["type"]
            if t == "mine":
                bubble(m["text"], m["ts"], "mine", mine=True)
            elif t == "chat" and m["from"] == "SERVER":
                sysline(f"{m['text']} · {hm(m['ts'])}")
            elif t == "chat":
                bubble(m["text"], m["ts"], "other", name=m["from"])
            elif t == "file":
                bubble(f"📎 {m['text']}", m["ts"], "file", name=m["from"])
            elif t == "myfile":
                bubble(f"📎 {m['text']}", m["ts"], "file", mine=True)
            elif t == "error":
                sysline(m["text"], "err")
            elif t == "info":
                sysline(m["text"])
    public_view()

with tab_priv:
    others = [u for u in conn.online if u != user]
    with st.form("pm", clear_on_submit=True):
        c1, c2 = st.columns([1, 3])
        to = c1.selectbox("To", others or ["(nobody online)"])
        txt = c2.text_input("Message")
        if st.form_submit_button("Send 🔒") and txt and others:
            conn.send(f"/msg {to} {txt}")

    @st.fragment(run_every=1)
    def private_view():
        for m in [x for x in list(conn.messages) if x["type"] in ("private", "myprivate")][-last_n:]:
            if m["type"] == "private":
                bubble(m["text"], m["ts"], "priv", name=f"{m['from']} (private)")
            else:
                bubble(m["text"], m["ts"], "priv", mine=True, name=f"to {m['to']}")
    private_view()

with tab_files:
    @st.fragment(run_every=2)
    def files_view():
        files = [(i, m) for i, m in enumerate(list(conn.messages)) if m["type"] == "file"]
        if not files:
            st.info("No files received yet.")
        for i, m in reversed(files):
            data = base64.b64decode(m["data"])
            a, b = st.columns([3, 1])
            a.markdown(f"**{esc(m['text'])}** \n{len(data)/1024:.1f} KB · from "
                       f"{esc(m['from'])} · {hm(m['ts'])}")
            b.download_button("⬇️", data, file_name=m["text"], key=f"dl{i}")
    files_view()

# ---------------- Input ----------------
if msg := st.chat_input("Message everyone  (or /list, /msg user text)"):
    conn.send(msg)
    if not msg.startswith("/"):
        conn.echo(type="mine", text=msg)
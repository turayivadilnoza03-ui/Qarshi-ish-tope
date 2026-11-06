#!/usr/bin/env python3
"""Qarshi Ish - ish izlovchilar va ish beruvchilar uchun sayt.
Ishga tushirish:  python3 server.py   ->  http://localhost:8000
Faqat Python 3 standart kutubxonasi kerak (SQLite ichida)."""
import json, sqlite3, os, hashlib, secrets, time, re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(DIR, "ish.db")
PORT = int(os.environ.get("PORT", 8000))

HTML = r'''<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qarshi Ish</title>
<style>
:root{--bg:#f4f6f8;--card:#fff;--pri:#0f766e;--pri2:#115e59;--txt:#1f2933;--mut:#6b7785;--line:#e3e8ee;--bad:#c0392b;--ok:#15803d}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--txt)}
header{background:var(--pri);color:#fff;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:5}
header h1{font-size:18px;margin:0}
header small{opacity:.85;margin-right:10px}
main{max-width:760px;margin:0 auto;padding:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:12px}
.tabs{display:flex;gap:8px;margin-bottom:12px}
.tabs button{flex:1}
button,.btn{background:var(--pri);color:#fff;border:0;border-radius:8px;padding:10px 14px;font-size:15px;cursor:pointer}
button:hover{background:var(--pri2)}
button.sec{background:#e6ecef;color:var(--txt)}
button.sec.on{background:var(--pri);color:#fff}
button.bad{background:var(--bad)}button.ok{background:var(--ok)}
button.link{background:none;color:#fff;padding:4px 8px;text-decoration:underline}
input,select,textarea{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:15px;font-family:inherit;margin:4px 0 10px;background:#fff}
textarea{min-height:80px;resize:vertical}
label{font-size:13px;color:var(--mut)}
.row{display:flex;gap:8px}.row>*{flex:1}
.tag{display:inline-block;background:#e6f4f1;color:var(--pri2);border-radius:20px;padding:2px 10px;font-size:12px;margin:2px 4px 2px 0}
.tag.pending{background:#fff4d6;color:#8a6100}.tag.accepted{background:#dcfce7;color:var(--ok)}
.tag.rejected,.tag.closed{background:#fde4e1;color:var(--bad)}
h3{margin:0 0 6px;font-size:17px}
.mut{color:var(--mut);font-size:13px}
.err{background:#fde4e1;color:var(--bad);padding:8px 12px;border-radius:8px;margin-bottom:10px}
.chat{display:flex;flex-direction:column;height:calc(100vh - 150px);min-height:340px}
.msgs{flex:1;overflow-y:auto;padding:6px}
.m{max-width:80%;padding:8px 12px;border-radius:14px;margin:4px 0;white-space:pre-wrap;word-wrap:break-word}
.m.me{background:var(--pri);color:#fff;margin-left:auto;border-bottom-right-radius:4px}
.m.ot{background:#fff;border:1px solid var(--line);border-bottom-left-radius:4px}
.m.sys{background:#fff8e1;border:1px solid #f1d98a;margin:8px auto;text-align:center;max-width:95%;font-weight:600}
.send{display:flex;gap:8px;margin-top:8px}.send input{margin:0}
.empty{text-align:center;color:var(--mut);padding:30px}
</style>
</head>
<body>
<header><h1>🧰 Qarshi Ish</h1><div id="hr"></div></header>
<main id="app"></main>
<script>
const CATS=["Qurilish","Savdo","Xizmat ko'rsatish","Oshxona / Kafe","Haydovchi","Dehqonchilik","Ta'mirlash","Tozalash","Ofis","Boshqa"];
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let S={token:localStorage.getItem("tk"),role:localStorage.getItem("rl"),name:localStorage.getItem("nm"),tab:"jobs",chat:null,timer:null,reg:false,open:null,openJob:null};
const STAT={pending:"Kutilmoqda",accepted:"Qabul qilindi",rejected:"Rad etildi",closed:"Yopilgan"};

async function api(path,method="GET",body){
  const r=await fetch("/api/"+path,{method,headers:{"Content-Type":"application/json",...(S.token?{Authorization:"Bearer "+S.token}:{})},body:body?JSON.stringify(body):undefined});
  const d=await r.json();
  if(r.status===401&&S.token){logout();throw new Error(d.error)}
  if(!r.ok)throw new Error(d.error||"Xatolik");
  return d;
}
function logout(){localStorage.clear();S.token=S.role=S.name=null;stopChat();render()}
function stopChat(){clearInterval(S.timer);S.chat=null}
function setTab(t){stopChat();S.tab=t;S.open=null;S.openJob=null;render()}

function render(){
  $("#hr").innerHTML=S.token?`<small>${esc(S.name)} · ${S.role==="worker"?"Ish izlovchi":"Ish beruvchi"}</small><button class="link" onclick="logout()">Chiqish</button>`:"";
  if(!S.token)return authView();
  if(S.chat)return chatView();
  if(S.role==="worker"){
    $("#app").innerHTML=`<div class="tabs"><button class="sec ${S.tab==="jobs"?"on":""}" onclick="setTab('jobs')">Ishlar</button><button class="sec ${S.tab==="apps"?"on":""}" onclick="setTab('apps')">Arizalarim</button></div><div id="v"></div>`;
    S.tab==="apps"?workerApps():workerJobs();
  }else{
    if(!["post","mine"].includes(S.tab))S.tab="mine";
    $("#app").innerHTML=`<div class="tabs"><button class="sec ${S.tab==="mine"?"on":""}" onclick="setTab('mine')">E'lonlarim</button><button class="sec ${S.tab==="post"?"on":""}" onclick="setTab('post')">+ E'lon berish</button></div><div id="v"></div>`;
    S.tab==="post"?postView():myJobs();
  }
}

/* ---------- Kirish ---------- */
function authView(){
  $("#app").innerHTML=`<div class="card"><h3>${S.reg?"Ro'yxatdan o'tish":"Kirish"}</h3><div id="e"></div>
  ${S.reg?`<label>Ismingiz</label><input id="n"><label>Kim sifatida?</label><select id="r"><option value="worker">Ish izlayman</option><option value="employer">Ish beraman</option></select>`:""}
  <label>Telefon raqam</label><input id="p" type="tel" placeholder="90 123 45 67">
  <label>Parol</label><input id="w" type="password">
  <button onclick="auth()" style="width:100%">${S.reg?"Ro'yxatdan o'tish":"Kirish"}</button>
  <p class="mut" style="text-align:center;cursor:pointer" onclick="S.reg=!S.reg;render()">${S.reg?"Akkauntingiz bormi? Kirish":"Akkaunt yo'qmi? Ro'yxatdan o'tish"}</p></div>`;
}
async function auth(){
  try{
    const b={phone:$("#p").value,password:$("#w").value};
    if(S.reg){b.name=$("#n").value;b.role=$("#r").value}
    const d=await api(S.reg?"register":"login","POST",b);
    S.token=d.token;S.role=d.role;S.name=d.name;
    localStorage.setItem("tk",d.token);localStorage.setItem("rl",d.role);localStorage.setItem("nm",d.name);
    S.tab=d.role==="worker"?"jobs":"mine";render();
  }catch(e){$("#e").innerHTML=`<div class="err">${esc(e.message)}</div>`}
}

/* ---------- Ish izlovchi ---------- */
let jobFilter={q:"",cat:""};
async function workerJobs(){
  $("#v").innerHTML=`<div class="row"><input id="fq" placeholder="Qidirish..." value="${esc(jobFilter.q)}"><select id="fc"><option value="">Barcha turlar</option>${CATS.map(c=>`<option ${c===jobFilter.cat?"selected":""}>${esc(c)}</option>`).join("")}</select></div><div id="list"></div>`;
  $("#fq").oninput=e=>{jobFilter.q=e.target.value;loadJobs()};$("#fc").onchange=e=>{jobFilter.cat=e.target.value;loadJobs()};
  loadJobs();
}
async function loadJobs(){
  const jobs=await api(`jobs?q=${encodeURIComponent(jobFilter.q)}&cat=${encodeURIComponent(jobFilter.cat)}`);
  $("#list").innerHTML=jobs.length?jobs.map(j=>`<div class="card"><h3>${esc(j.title)}</h3>
   <span class="tag">${esc(j.category||"Boshqa")}</span>${j.salary?`<span class="tag">💰 ${esc(j.salary)}</span>`:""}${j.district?`<span class="tag">📍 ${esc(j.district)}</span>`:""}
   <p>${esc(j.description).slice(0,S.openJob===j.id?9999:140)}${S.openJob!==j.id&&j.description.length>140?"…":""}</p>
   ${S.openJob===j.id?`${j.requirements?`<p><b>Talablar:</b> ${esc(j.requirements)}</p>`:""}${j.schedule?`<p><b>Ish vaqti:</b> ${esc(j.schedule)}</p>`:""}<p class="mut">E'lon beruvchi: ${esc(j.employer)} · Manzil ma'qul topilgach yuboriladi</p>
     ${j.my_status?`<span class="tag ${j.my_status}">Ariza: ${STAT[j.my_status]}</span>`:`<textarea id="m${j.id}" placeholder="O'zingiz haqingizda qisqacha yozing (tajriba, qachon boshlay olasiz...)"></textarea><button onclick="apply(${j.id})">Ariza yuborish</button>`}`
   :`<button class="sec" onclick="S.openJob=${j.id};loadJobs()">Batafsil</button>`}</div>`).join(""):`<div class="empty">Hozircha ish e'lonlari yo'q</div>`;
}
async function apply(id){
  try{const d=await api(`jobs/${id}/apply`,"POST",{message:$("#m"+id).value});openChat(d.app_id)}catch(e){alert(e.message)}
}
async function workerApps(){
  const a=await api("my/applications");
  $("#v").innerHTML=a.length?a.map(x=>`<div class="card"><h3>${esc(x.title)}</h3><span class="tag ${x.status}">${STAT[x.status]}</span><span class="mut">${esc(x.employer)}</span>
   ${x.address?`<p>📍 <b>Manzil:</b> ${esc(x.address)}</p>`:""}<button onclick="openChat(${x.id})">💬 Chat</button></div>`).join(""):`<div class="empty">Hali ariza bermagansiz</div>`;
}

/* ---------- Ish beruvchi ---------- */
function postView(){
  $("#v").innerHTML=`<div class="card"><h3>Yangi e'lon</h3><div id="e"></div>
  <label>Lavozim / ish nomi *</label><input id="t" placeholder="Masalan: Quruvchi yordamchisi">
  <div class="row"><div><label>Tur</label><select id="c">${CATS.map(c=>`<option>${esc(c)}</option>`).join("")}</select></div><div><label>Maosh</label><input id="s" placeholder="Masalan: kuniga 150 000 so'm"></div></div>
  <label>Tuman / mahalla</label><input id="d" placeholder="Masalan: Qarshi sh., Nasaf ko'chasi">
  <label>Ish tavsifi *</label><textarea id="ds" placeholder="Nima ish qilinadi?"></textarea>
  <label>Talablar</label><textarea id="rq" placeholder="Tajriba, yosh, ko'nikmalar..."></textarea>
  <label>Ish vaqti</label><input id="sc" placeholder="Masalan: 08:00 – 17:00, dam olish yakshanba">
  <label>To'liq manzil * (faqat ma'qul topilgan ishchiga yuboriladi)</label><input id="ad">
  <button onclick="postJob()" style="width:100%">E'lonni joylash</button></div>`;
}
async function postJob(){
  try{await api("jobs","POST",{title:$("#t").value,category:$("#c").value,salary:$("#s").value,district:$("#d").value,description:$("#ds").value,requirements:$("#rq").value,schedule:$("#sc").value,address:$("#ad").value});setTab("mine")}
  catch(e){$("#e").innerHTML=`<div class="err">${esc(e.message)}</div>`}
}
async function myJobs(){
  const js=await api("my/jobs");
  $("#v").innerHTML=js.length?js.map(j=>`<div class="card"><h3>${esc(j.title)}</h3><span class="tag ${j.status==="open"?"":"closed"}">${j.status==="open"?"Faol":"Yopilgan"}</span><span class="tag">${j.apps} ta ariza</span>
   <div style="margin-top:8px"><button class="sec" onclick="toggleApps(${j.id})">Arizalar</button> ${j.status==="open"?`<button class="bad" onclick="delJob(${j.id})">Olib tashlash</button>`:""}</div><div id="ap${j.id}"></div></div>`).join(""):`<div class="empty">Hali e'lon bermagansiz</div>`;
  if(S.open)toggleApps(S.open,true);
}
async function toggleApps(id,keep){
  const el=$("#ap"+id);if(!el)return;
  if(!keep&&S.open===id){S.open=null;el.innerHTML="";return}
  S.open=id;const a=await api(`jobs/${id}/applications`);
  el.innerHTML=a.length?a.map(x=>`<div style="border-top:1px solid var(--line);margin-top:10px;padding-top:8px"><b>${esc(x.name)}</b> <span class="tag ${x.status}">${STAT[x.status]}</span><br><span class="mut">📞 ${esc(x.phone)}</span><p>${esc(x.message)}</p><button onclick="openChat(${x.id})">💬 Chat</button></div>`).join(""):`<p class="mut">Hozircha ariza yo'q</p>`;
}
async function delJob(id){if(confirm("E'lonni olib tashlaysizmi?")){await api("jobs/"+id,"DELETE");myJobs()}}

/* ---------- Chat ---------- */
function openChat(id){S.chat={id,last:0,info:null};render()}
function chatView(){
  $("#app").innerHTML=`<button class="sec" onclick="stopChat();render()" style="margin-bottom:10px">← Orqaga</button><div class="card chat"><div id="ch" style="margin-bottom:6px"></div><div class="msgs" id="ms"></div><div id="act"></div><div class="send"><input id="tx" placeholder="Xabar yozing..." onkeydown="if(event.key==='Enter')sendMsg()"><button onclick="sendMsg()">Yuborish</button></div></div>`;
  S.chat.last=0;pollChat();clearInterval(S.timer);S.timer=setInterval(pollChat,2500);
}
async function pollChat(){
  if(!S.chat)return;
  try{
    const d=await api(`apps/${S.chat.id}/messages?after=${S.chat.last}`);
    S.chat.info=d;const box=$("#ms");if(!box)return;
    $("#ch").innerHTML=`<h3>${esc(d.title)}</h3><span class="mut">${esc(d.other)}</span> <span class="tag ${d.status}">${STAT[d.status]}</span>`;
    const near=box.scrollHeight-box.scrollTop-box.clientHeight<80||S.chat.last===0;
    d.messages.forEach(m=>{S.chat.last=m.id;const e=document.createElement("div");e.className="m "+(m.system?"sys":m.sender_id===d.me?"me":"ot");e.textContent=m.text;box.appendChild(e)});
    if(near)box.scrollTop=box.scrollHeight;
    $("#act").innerHTML=d.is_employer&&d.status==="pending"?`<div class="row" style="margin-top:6px"><button class="ok" onclick="decide('accept')">✅ Ma'qul — manzilni yuborish</button><button class="bad" onclick="decide('reject')">❌ Rad etish</button></div>`:"";
  }catch(e){}
}
async function sendMsg(){
  const t=$("#tx").value.trim();if(!t)return;$("#tx").value="";
  try{await api(`apps/${S.chat.id}/messages`,"POST",{text:t});pollChat()}catch(e){alert(e.message)}
}
async function decide(a){
  if(a==="accept"&&!confirm("Ishchiga manzil yuboriladi va e'lon olib tashlanadi. Davom etasizmi?"))return;
  try{await api(`apps/${S.chat.id}/${a}`,"POST");pollChat()}catch(e){alert(e.message)}
}
render();
</script>
</body>
</html>
'''

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT, phone TEXT UNIQUE, pw TEXT, salt TEXT,
  role TEXT, token TEXT);
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY, employer_id INTEGER, title TEXT, category TEXT,
  salary TEXT, district TEXT, description TEXT, requirements TEXT,
  schedule TEXT, address TEXT, status TEXT DEFAULT 'open', created REAL);
CREATE TABLE IF NOT EXISTS applications(
  id INTEGER PRIMARY KEY, job_id INTEGER, worker_id INTEGER, message TEXT,
  status TEXT DEFAULT 'pending', created REAL, UNIQUE(job_id, worker_id));
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, app_id INTEGER, sender_id INTEGER, text TEXT,
  system INTEGER DEFAULT 0, created REAL);
"""

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.executescript(SCHEMA)

def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100_000).hex()

def norm_phone(p):
    return re.sub(r"\D", "", p or "")

class Err(Exception):
    def __init__(self, code, msg):
        self.code, self.msg = code, msg

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    # ---------- yordamchilar ----------
    def send_json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n: return {}
        try: return json.loads(self.rfile.read(n))
        except Exception: raise Err(400, "Noto'g'ri so'rov")

    def user(self, c, required=True):
        t = (self.headers.get("Authorization") or "").replace("Bearer ", "")
        u = c.execute("SELECT * FROM users WHERE token=?", (t,)).fetchone() if t else None
        if required and not u: raise Err(401, "Avval tizimga kiring")
        return u

    def handle_any(self, method):
        path, _, qs = self.path.partition("?")
        params = {}
        for kv in qs.split("&"):
            if "=" in kv:
                from urllib.parse import unquote_plus
                k, v = kv.split("=", 1)
                params[k] = unquote_plus(v)
        try:
            if not path.startswith("/api/"):
                if method == "GET": return self.static(path)
                raise Err(404, "Topilmadi")
            with db() as c:
                res = self.route(c, method, path[5:].strip("/").split("/"), params)
            self.send_json(res)
        except Err as e:
            self.send_json({"error": e.msg}, e.code)
        except Exception as e:
            self.send_json({"error": "Server xatosi: %s" % e}, 500)

    def do_GET(self): self.handle_any("GET")
    def do_POST(self): self.handle_any("POST")
    def do_DELETE(self): self.handle_any("DELETE")

    def static(self, path):
        data = HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ---------- marshrutlar ----------
    def route(self, c, m, p, q):
        if p == ["register"] and m == "POST":
            d = self.body()
            name = (d.get("name") or "").strip()
            phone = norm_phone(d.get("phone"))
            pw = d.get("password") or ""
            role = d.get("role")
            if not name or len(phone) < 9 or len(pw) < 4 or role not in ("worker", "employer"):
                raise Err(400, "Ism, telefon (kamida 9 raqam), parol (kamida 4 belgi) va rolni to'g'ri kiriting")
            if c.execute("SELECT 1 FROM users WHERE phone=?", (phone,)).fetchone():
                raise Err(400, "Bu telefon raqam ro'yxatdan o'tgan")
            salt, token = secrets.token_hex(8), secrets.token_hex(24)
            c.execute("INSERT INTO users(name,phone,pw,salt,role,token) VALUES(?,?,?,?,?,?)",
                      (name, phone, hash_pw(pw, salt), salt, role, token))
            return {"token": token, "name": name, "role": role}

        if p == ["login"] and m == "POST":
            d = self.body()
            u = c.execute("SELECT * FROM users WHERE phone=?", (norm_phone(d.get("phone")),)).fetchone()
            if not u or hash_pw(d.get("password") or "", u["salt"]) != u["pw"]:
                raise Err(401, "Telefon yoki parol noto'g'ri")
            token = secrets.token_hex(24)
            c.execute("UPDATE users SET token=? WHERE id=?", (token, u["id"]))
            return {"token": token, "name": u["name"], "role": u["role"]}

        u = self.user(c)

        if p == ["me"]:
            return {"id": u["id"], "name": u["name"], "role": u["role"], "phone": u["phone"]}

        # Ochiq e'lonlar (manzil yashirin!)
        if p == ["jobs"] and m == "GET":
            sql = ("SELECT j.id,j.title,j.category,j.salary,j.district,j.description,j.requirements,"
                   "j.schedule,j.created,u.name AS employer,"
                   "(SELECT status FROM applications a WHERE a.job_id=j.id AND a.worker_id=?) AS my_status "
                   "FROM jobs j JOIN users u ON u.id=j.employer_id WHERE j.status='open'")
            args = [u["id"]]
            if q.get("cat"): sql += " AND j.category=?"; args.append(q["cat"])
            if q.get("q"):
                sql += " AND (j.title LIKE ? OR j.description LIKE ?)"
                args += ["%" + q["q"] + "%"] * 2
            sql += " ORDER BY j.created DESC"
            return [dict(r) for r in c.execute(sql, args)]

        # E'lon berish
        if p == ["jobs"] and m == "POST":
            if u["role"] != "employer": raise Err(403, "Faqat ish beruvchi e'lon bera oladi")
            d = self.body()
            f = {k: (d.get(k) or "").strip() for k in
                 ("title", "category", "salary", "district", "description", "requirements", "schedule", "address")}
            if not f["title"] or not f["description"] or not f["address"]:
                raise Err(400, "Lavozim, tavsif va manzilni to'ldiring")
            c.execute("INSERT INTO jobs(employer_id,title,category,salary,district,description,requirements,"
                      "schedule,address,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (u["id"], f["title"], f["category"], f["salary"], f["district"], f["description"],
                       f["requirements"], f["schedule"], f["address"], time.time()))
            return {"ok": True}

        # Ish beruvchining e'lonlari
        if p == ["my", "jobs"]:
            rows = c.execute(
                "SELECT j.*,(SELECT COUNT(*) FROM applications a WHERE a.job_id=j.id) AS apps "
                "FROM jobs j WHERE employer_id=? ORDER BY created DESC", (u["id"],)).fetchall()
            return [dict(r) for r in rows]

        # E'lonni olib tashlash
        if len(p) == 2 and p[0] == "jobs" and m == "DELETE":
            j = c.execute("SELECT * FROM jobs WHERE id=? AND employer_id=?", (p[1], u["id"])).fetchone()
            if not j: raise Err(404, "E'lon topilmadi")
            c.execute("UPDATE jobs SET status='closed' WHERE id=?", (j["id"],))
            return {"ok": True}

        # Ariza berish
        if len(p) == 3 and p[0] == "jobs" and p[2] == "apply" and m == "POST":
            if u["role"] != "worker": raise Err(403, "Faqat ish izlovchi ariza bera oladi")
            j = c.execute("SELECT * FROM jobs WHERE id=? AND status='open'", (p[1],)).fetchone()
            if not j: raise Err(404, "E'lon topilmadi yoki olib tashlangan")
            msg = (self.body().get("message") or "").strip() or "Salom! Bu ish menga qiziq."
            try:
                cur = c.execute("INSERT INTO applications(job_id,worker_id,message,created) VALUES(?,?,?,?)",
                                (j["id"], u["id"], msg, time.time()))
            except sqlite3.IntegrityError:
                raise Err(400, "Siz bu ishga allaqachon ariza bergansiz")
            c.execute("INSERT INTO messages(app_id,sender_id,text,created) VALUES(?,?,?,?)",
                      (cur.lastrowid, u["id"], msg, time.time()))
            return {"ok": True, "app_id": cur.lastrowid}

        # Ish izlovchining arizalari
        if p == ["my", "applications"]:
            rows = c.execute(
                "SELECT a.id,a.status,a.created,j.title,j.salary,j.district,j.status AS job_status,"
                "CASE WHEN a.status='accepted' THEN j.address END AS address,u.name AS employer "
                "FROM applications a JOIN jobs j ON j.id=a.job_id JOIN users u ON u.id=j.employer_id "
                "WHERE a.worker_id=? ORDER BY a.created DESC", (u["id"],)).fetchall()
            return [dict(r) for r in rows]

        # E'londagi arizalar (ish beruvchi)
        if len(p) == 3 and p[0] == "jobs" and p[2] == "applications":
            j = c.execute("SELECT * FROM jobs WHERE id=? AND employer_id=?", (p[1], u["id"])).fetchone()
            if not j: raise Err(404, "E'lon topilmadi")
            rows = c.execute(
                "SELECT a.id,a.status,a.message,a.created,w.name,w.phone FROM applications a "
                "JOIN users w ON w.id=a.worker_id WHERE a.job_id=? ORDER BY a.created DESC", (j["id"],)).fetchall()
            return [dict(r) for r in rows]

        # Chat
        if len(p) == 3 and p[0] == "apps":
            a = c.execute("SELECT a.*,j.employer_id,j.address,j.title FROM applications a "
                          "JOIN jobs j ON j.id=a.job_id WHERE a.id=?", (p[1],)).fetchone()
            if not a or u["id"] not in (a["worker_id"], a["employer_id"]):
                raise Err(404, "Suhbat topilmadi")
            is_emp = u["id"] == a["employer_id"]

            if p[2] == "messages" and m == "GET":
                after = int(q.get("after") or 0)
                msgs = c.execute("SELECT id,sender_id,text,system,created FROM messages "
                                 "WHERE app_id=? AND id>? ORDER BY id", (a["id"], after)).fetchall()
                other = c.execute("SELECT name FROM users WHERE id=?",
                                  (a["worker_id"] if is_emp else a["employer_id"],)).fetchone()
                return {"me": u["id"], "status": a["status"], "title": a["title"],
                        "other": other["name"], "is_employer": is_emp,
                        "messages": [dict(r) for r in msgs]}

            if p[2] == "messages" and m == "POST":
                if a["status"] in ("rejected", "closed"): raise Err(400, "Suhbat yopilgan")
                t = (self.body().get("text") or "").strip()
                if not t: raise Err(400, "Xabar bo'sh")
                c.execute("INSERT INTO messages(app_id,sender_id,text,created) VALUES(?,?,?,?)",
                          (a["id"], u["id"], t[:2000], time.time()))
                return {"ok": True}

            if p[2] == "accept" and m == "POST":
                if not is_emp: raise Err(403, "Ruxsat yo'q")
                if a["status"] != "pending": raise Err(400, "Allaqachon ko'rib chiqilgan")
                c.execute("UPDATE applications SET status='accepted' WHERE id=?", (a["id"],))
                # E'lon olib tashlanadi, qolgan arizalar yopiladi
                c.execute("UPDATE jobs SET status='closed' WHERE id=?", (a["job_id"],))
                c.execute("UPDATE applications SET status='closed' WHERE job_id=? AND id<>? AND status='pending'",
                          (a["job_id"], a["id"]))
                c.execute("INSERT INTO messages(app_id,sender_id,text,system,created) VALUES(?,?,?,1,?)",
                          (a["id"], u["id"], "✅ Arizangiz ma'qul topildi! Ish manzili: " + a["address"], time.time()))
                return {"ok": True}

            if p[2] == "reject" and m == "POST":
                if not is_emp: raise Err(403, "Ruxsat yo'q")
                if a["status"] != "pending": raise Err(400, "Allaqachon ko'rib chiqilgan")
                c.execute("UPDATE applications SET status='rejected' WHERE id=?", (a["id"],))
                c.execute("INSERT INTO messages(app_id,sender_id,text,system,created) VALUES(?,?,?,1,?)",
                          (a["id"], u["id"], "❌ Afsus, arizangiz rad etildi.", time.time()))
                return {"ok": True}

        raise Err(404, "Topilmadi")

if __name__ == "__main__":
    print("Qarshi Ish ishga tushdi: http://localhost:%d" % PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()

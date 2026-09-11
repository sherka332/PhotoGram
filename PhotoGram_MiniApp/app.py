import os, sqlite3, secrets
from functools import wraps
from flask import Flask, request, jsonify, render_template, session
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps


app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY",secrets.token_hex(32))
DB=os.environ.get("DATABASE_PATH","photogram.db")
UPLOAD="static/uploads"; os.makedirs(UPLOAD,exist_ok=True)
ADMIN_IDS={x.strip() for x in os.environ.get("ADMIN_IDS","").split(",") if x.strip()}

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
    c=conn(); c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,tg_id TEXT UNIQUE,username TEXT,name TEXT,bio TEXT DEFAULT '',avatar TEXT DEFAULT '',is_admin INTEGER DEFAULT 0,is_banned INTEGER DEFAULT 0,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,image TEXT,caption TEXT DEFAULT '',hidden INTEGER DEFAULT 0,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS likes(user_id INTEGER,post_id INTEGER,UNIQUE(user_id,post_id));
    CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,post_id INTEGER,text TEXT,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS follows(follower INTEGER,following INTEGER,UNIQUE(follower,following));
    CREATE TABLE IF NOT EXISTS saves(user_id INTEGER,post_id INTEGER,UNIQUE(user_id,post_id));
    CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,post_id INTEGER,reason TEXT,status TEXT DEFAULT 'open',created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,actor_id INTEGER,kind TEXT,post_id INTEGER,read INTEGER DEFAULT 0,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,sender_id INTEGER,receiver_id INTEGER,text TEXT,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
    """); c.commit(); c.close()
init()
def user():
    if not session.get("uid"): return None
    c=conn(); u=c.execute("SELECT * FROM users WHERE id=?",(session["uid"],)).fetchone(); c.close(); return dict(u) if u else None
def admin(f):
    @wraps(f)
    def w(*a,**k):
        u=user()
        if not u or not u["is_admin"]: return jsonify(error="Admin ruxsati kerak"),403
        return f(*a,**k)
    return w

@app.get("/")
def home(): return render_template("index.html")
@app.get("/admin")
def admin_page(): return render_template("admin.html")

@app.post("/api/login")
def login():
    d=request.json or {}; tg=str(d.get("tg_id","demo")); un=d.get("username") or "user"; name=d.get("name") or un
    c=conn(); u=c.execute("SELECT * FROM users WHERE tg_id=?",(tg,)).fetchone()
    if not u:
        c.execute("INSERT INTO users(tg_id,username,name,is_admin) VALUES(?,?,?,?)",(tg,un,name,1 if tg in ADMIN_IDS else 0)); c.commit(); u=c.execute("SELECT * FROM users WHERE tg_id=?",(tg,)).fetchone()
    if u["is_banned"]: c.close(); return jsonify(error="Hisob bloklangan"),403
    session["uid"]=u["id"]; c.close(); return jsonify(user=dict(u))
@app.get("/api/me")
def me(): return jsonify(user=user())

@app.get("/api/feed")
def feed():
    u=user(); uid=u["id"] if u else 0; c=conn()
    r=c.execute("""SELECT p.*,u.username,u.name,u.avatar,
    (SELECT COUNT(*) FROM likes WHERE post_id=p.id) likes,
    EXISTS(SELECT 1 FROM likes WHERE post_id=p.id AND user_id=?) liked,
    (SELECT COUNT(*) FROM comments WHERE post_id=p.id) comments,
    EXISTS(SELECT 1 FROM saves WHERE post_id=p.id AND user_id=?) saved
    FROM posts p JOIN users u ON u.id=p.user_id
    WHERE p.hidden=0 AND u.is_banned=0 ORDER BY p.id DESC""",(uid,uid)).fetchall(); c.close()
    return jsonify(posts=[dict(x) for x in r])

@app.post("/api/posts")
def create_post():
    u=user()
    if not u:return jsonify(error="Login kerak"),401
    f=request.files.get("image")
    if not f:return jsonify(error="Rasm tanlang"),400
    ext=os.path.splitext(secure_filename(f.filename))[1].lower()
    if ext not in {".jpg",".jpeg",".png",".webp",".gif"}:return jsonify(error="Faqat rasm fayllar"),400
    name=secrets.token_hex(12)+ext; name = f"{uuid.uuid4().hex}.jpg"
output_path = os.path.join(app.config["UPLOAD_FOLDER"], name)

try:
    f.stream.seek(0)

    with Image.open(f.stream) as img:
        img = ImageOps.exif_transpose(img)

        # Juda katta rasmni kichraytiradi
        max_side = 2560

        if max(img.size) > max_side:
            ratio = max_side / max(img.size)

            new_size = (
                max(1, int(img.width * ratio)),
                max(1, int(img.height * ratio))
            )

            img = img.resize(
                new_size,
                Image.Resampling.LANCZOS
            )

        # Shaffof PNG/WebP rasmlarni oq fon bilan JPEGga o'tkazadi
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, "white")
            bg.paste(
                img.convert("RGB"),
                mask=img.getchannel("A")
            )
            img = bg
        else:
            img = img.convert("RGB")

        # Yuqori sifatli JPEG
        img.save(
            output_path,
            "JPEG",
            quality=88,
            optimize=True,
            progressive=True
        )

except Exception:
    return jsonify(
        {"error": "Rasmni qayta ishlashda xatolik"}
    ), 400


    c=conn(); c.execute("INSERT INTO posts(user_id,image,caption) VALUES(?,?,?)",(u["id"],"/static/uploads/"+name,request.form.get("caption","").strip())); c.commit(); c.close()
    return jsonify(ok=True)

def toggle(table,uid,pid):
    c=conn(); x=c.execute(f"SELECT 1 FROM {table} WHERE user_id=? AND post_id=?",(uid,pid)).fetchone()
    if x:c.execute(f"DELETE FROM {table} WHERE user_id=? AND post_id=?",(uid,pid))
    else:c.execute(f"INSERT OR IGNORE INTO {table}(user_id,post_id) VALUES(?,?)",(uid,pid))
    c.commit(); c.close()
@app.post("/api/posts/<int:pid>/like")
def like(pid): toggle("likes",user()["id"],pid); return jsonify(ok=True)
@app.post("/api/posts/<int:pid>/save")
def save(pid): toggle("saves",user()["id"],pid); return jsonify(ok=True)
@app.get("/api/posts/<int:pid>/comments")
def comments(pid):
    c=conn(); r=c.execute("SELECT cm.*,u.username,u.name FROM comments cm JOIN users u ON u.id=cm.user_id WHERE cm.post_id=? ORDER BY cm.id",(pid,)).fetchall(); c.close()
    return jsonify(comments=[dict(x) for x in r])
@app.post("/api/posts/<int:pid>/comments")
def add_comment(pid):
    u=user(); t=(request.json or {}).get("text","").strip()
    if not t:return jsonify(error="Bo'sh komment"),400
    c=conn(); c.execute("INSERT INTO comments(user_id,post_id,text) VALUES(?,?,?)",(u["id"],pid,t)); c.commit(); c.close(); return jsonify(ok=True)
@app.post("/api/posts/<int:pid>/report")
def report(pid):
    u=user(); reason=(request.json or {}).get("reason","Boshqa").strip()
    c=conn(); c.execute("INSERT INTO reports(user_id,post_id,reason) VALUES(?,?,?)",(u["id"],pid,reason or "Boshqa")); c.commit(); c.close(); return jsonify(ok=True)

@app.get("/api/users")
def users():
    q=request.args.get("q",""); c=conn(); r=c.execute("SELECT id,username,name,bio,avatar FROM users WHERE is_banned=0 AND (username LIKE ? OR name LIKE ?) LIMIT 40",(f"%{q}%",f"%{q}%")).fetchall(); c.close()
    return jsonify(users=[dict(x) for x in r])
@app.get("/api/users/<int:uid>")
def profile(uid):
    me=user(); mid=me["id"] if me else 0; c=conn(); u=c.execute("SELECT id,username,name,bio,avatar FROM users WHERE id=?",(uid,)).fetchone()
    if not u:c.close(); return jsonify(error="Topilmadi"),404
    p=c.execute("""SELECT p.*,
        (SELECT COUNT(*) FROM likes WHERE post_id=p.id) likes,
        (SELECT COUNT(*) FROM comments WHERE post_id=p.id) comments,
        EXISTS(SELECT 1 FROM saves WHERE post_id=p.id AND user_id=?) saved
        FROM posts p WHERE p.user_id=? AND p.hidden=0 ORDER BY p.id DESC""",(mid,uid)).fetchall()
    fo=c.execute("SELECT COUNT(*) n FROM follows WHERE following=?",(uid,)).fetchone()["n"]; fi=c.execute("SELECT COUNT(*) n FROM follows WHERE follower=?",(uid,)).fetchone()["n"]
    isf=bool(c.execute("SELECT 1 FROM follows WHERE follower=? AND following=?",(mid,uid)).fetchone()) if mid else False
    c.close(); return jsonify(user=dict(u),posts=[dict(x) for x in p],followers=fo,following=fi,is_following=isf)
@app.post("/api/users/<int:uid>/follow")
def follow(uid):
    u=user(); c=conn(); x=c.execute("SELECT 1 FROM follows WHERE follower=? AND following=?",(u["id"],uid)).fetchone()
    if x:c.execute("DELETE FROM follows WHERE follower=? AND following=?",(u["id"],uid))
    else:c.execute("INSERT OR IGNORE INTO follows VALUES(?,?)",(u["id"],uid))
    c.commit(); c.close(); return jsonify(ok=True)

@app.get("/api/notifications")
def notifications():
    u=user(); c=conn(); r=c.execute("SELECT n.*,a.username actor FROM notifications n JOIN users a ON a.id=n.actor_id WHERE n.user_id=? ORDER BY n.id DESC LIMIT 50",(u["id"],)).fetchall(); c.close(); return jsonify(items=[dict(x) for x in r])
@app.get("/api/chats/<int:uid>")
def chat(uid):
    u=user(); c=conn(); r=c.execute("SELECT m.*,s.username sender FROM messages m JOIN users s ON s.id=m.sender_id WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?) ORDER BY m.id",(u["id"],uid,uid,u["id"])).fetchall(); c.close(); return jsonify(messages=[dict(x) for x in r])
@app.post("/api/chats/<int:uid>")
def send(uid):
    u=user(); t=(request.json or {}).get("text","").strip()
    if not t:return jsonify(error="Bo'sh xabar"),400
    c=conn(); c.execute("INSERT INTO messages(sender_id,receiver_id,text) VALUES(?,?,?)",(u["id"],uid,t)); c.commit(); c.close(); return jsonify(ok=True)

@app.get("/api/admin/stats")
@admin
def stats():
    c=conn(); out={k:c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"] for k,t in [("users","users"),("posts","posts"),("comments","comments"),("reports","reports")]}
    c.close(); return jsonify(out)
@app.get("/api/admin/users")
@admin
def a_users():
    c=conn(); r=c.execute("SELECT id,tg_id,username,name,is_admin,is_banned,created_at FROM users ORDER BY id DESC").fetchall(); c.close(); return jsonify(users=[dict(x) for x in r])
@app.post("/api/admin/users/<int:uid>/ban")
@admin
def ban(uid):
    c=conn(); c.execute("UPDATE users SET is_banned=CASE is_banned WHEN 1 THEN 0 ELSE 1 END WHERE id=?",(uid,)); c.commit(); c.close(); return jsonify(ok=True)
@app.get("/api/admin/posts")
@admin
def a_posts():
    c=conn(); r=c.execute("SELECT p.*,u.username FROM posts p JOIN users u ON u.id=p.user_id ORDER BY p.id DESC").fetchall(); c.close(); return jsonify(posts=[dict(x) for x in r])
@app.delete("/api/admin/posts/<int:pid>")
@admin
def delpost(pid):
    c=conn(); c.execute("DELETE FROM posts WHERE id=?",(pid,)); c.commit(); c.close(); return jsonify(ok=True)
@app.get("/api/admin/reports")
@admin
def a_reports():
    c=conn(); r=c.execute("SELECT r.*,u.username reporter,p.image,p.caption FROM reports r JOIN users u ON u.id=r.user_id JOIN posts p ON p.id=r.post_id ORDER BY r.id DESC").fetchall(); c.close(); return jsonify(reports=[dict(x) for x in r])
@app.post("/api/admin/reports/<int:rid>/close")
@admin
def close(rid):
    c=conn(); c.execute("UPDATE reports SET status='closed' WHERE id=?",(rid,)); c.commit(); c.close(); return jsonify(ok=True)

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))

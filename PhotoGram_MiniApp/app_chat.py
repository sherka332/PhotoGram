import os, uuid, hashlib, hmac, json
from datetime import datetime
from urllib.parse import parse_qsl

from flask import Flask, render_template, request, jsonify, session, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL") or "sqlite:///photogram.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
ADMIN_ID = str(os.getenv("ADMIN_ID", "0"))
ALLOWED_EXTENSIONS = {"png","jpg","jpeg","webp","gif"}

followers = db.Table("followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("following_id", db.Integer, db.ForeignKey("users.id"), primary_key=True)
)

likes = db.Table("likes",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("post_id", db.Integer, db.ForeignKey("posts.id"), primary_key=True)
)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    telegram_id = db.Column(db.String(40), unique=True, nullable=False)
    first_name = db.Column(db.String(100), default="User")
    username = db.Column(db.String(100), nullable=True)
    photo_url = db.Column(db.String(500), nullable=True)
    bio = db.Column(db.String(300), default="")
    verified = db.Column(db.Boolean, default=False)
    banned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship("Post", backref="author", lazy=True, cascade="all, delete-orphan")
    following = db.relationship("User", secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.following_id == id),
        backref=db.backref("followers", lazy="dynamic"), lazy="dynamic")

class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(1000), default="")
    hidden = db.Column(db.Boolean, default=False)
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comments = db.relationship("Comment", backref="post", lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    user = db.relationship("User")

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    text = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])

class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    reason = db.Column(db.String(500), default="Nomaqbul kontent")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True)
    resolved = db.Column(db.Boolean, default=False)

class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.String(1000), default="")

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def current_user():
    uid = session.get("uid")
    return db.session.get(User, uid) if uid else None

def is_admin():
    u = current_user()
    return bool(u and str(u.telegram_id) == ADMIN_ID)

def require_user():
    u = current_user()
    if not u or u.banned:
        return None
    return u

def user_json(u):
    if not u: return None
    return {
        "id": u.id, "telegram_id": u.telegram_id, "first_name": u.first_name,
        "username": u.username, "photo_url": u.photo_url, "bio": u.bio,
        "verified": u.verified, "banned": u.banned,
        "posts": len(u.posts), "followers": u.followers.count(), "following": u.following.count(),
        "is_admin": str(u.telegram_id) == ADMIN_ID
    }

def post_json(p, viewer=None):
    author = p.author
    liked = False
    if viewer:
        liked = db.session.execute(db.select(likes).where(
            likes.c.user_id == viewer.id, likes.c.post_id == p.id)).first() is not None
    return {
        "id": p.id, "image": p.image, "caption": p.caption, "hidden": p.hidden,
        "pinned": p.pinned, "created_at": p.created_at.isoformat(),
        "user": user_json(author), "likes": db.session.execute(
            db.select(db.func.count()).select_from(likes).where(likes.c.post_id == p.id)).scalar() or 0,
        "liked": liked, "comments": len(p.comments), "is_owner": bool(viewer and viewer.id == p.user_id)
    }

@app.route("/")
def index(): return render_template("index.html")

@app.route("/admin")
def admin_page(): return render_template("admin.html")

@app.route("/api/login", methods=["POST"])
def login():
    # Productionda Telegram initData HMAC tekshiruvi qo'shilishi kerak.
    data = request.get_json(force=True)
    tg_id = str(data.get("telegram_id", "")).strip()
    if not tg_id: return jsonify({"error":"Telegram user topilmadi"}), 400
    u = User.query.filter_by(telegram_id=tg_id).first()
    if not u:
        u = User(telegram_id=tg_id)
        db.session.add(u)
    u.first_name = (data.get("first_name") or u.first_name)[:100]
    u.username = (data.get("username") or u.username or "")[:100] or None
    u.photo_url = (data.get("photo_url") or u.photo_url or "")[:500] or None
    db.session.commit()
    if u.banned: return jsonify({"error":"Siz bloklangansiz"}), 403
    session["uid"] = u.id
    return jsonify({"user":user_json(u)})

@app.route("/api/me")
def me():
    return jsonify({"user":user_json(current_user())})

@app.route("/api/feed")
def feed():
    u = current_user()
    posts = Post.query.filter_by(hidden=False).order_by(Post.pinned.desc(), Post.created_at.desc()).limit(100).all()
    return jsonify({"posts":[post_json(p,u) for p in posts]})

@app.route("/api/posts", methods=["POST"])
def create_post():
    u = require_user()
    if not u: return jsonify({"error":"Avval tizimga kiring"}), 401
    if "image" not in request.files: return jsonify({"error":"Rasm tanlanmadi"}), 400
    f = request.files["image"]
    if not f.filename or not allowed(f.filename): return jsonify({"error":"Faqat PNG, JPG, JPEG, WEBP yoki GIF"}), 400
    ext = secure_filename(f.filename).rsplit(".",1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(app.config["UPLOAD_FOLDER"], name))
    caption = request.form.get("caption","")[:1000]
    p = Post(image=f"/static/uploads/{name}", caption=caption, user_id=u.id)
    db.session.add(p); db.session.commit()
    return jsonify({"post":post_json(p,u)})

@app.route("/api/posts/<int:pid>/like", methods=["POST"])
def toggle_like(pid):
    u = require_user()
    if not u: return jsonify({"error":"Login qiling"}), 401
    p = db.session.get(Post,pid)
    if not p: abort(404)
    row = db.session.execute(db.select(likes).where(likes.c.user_id==u.id, likes.c.post_id==pid)).first()
    if row:
        db.session.execute(likes.delete().where(likes.c.user_id==u.id, likes.c.post_id==pid))
        liked=False
    else:
        db.session.execute(likes.insert().values(user_id=u.id,post_id=pid)); liked=True
    db.session.commit()
    count=db.session.execute(db.select(db.func.count()).select_from(likes).where(likes.c.post_id==pid)).scalar()
    return jsonify({"liked":liked,"likes":count})

@app.route("/api/posts/<int:pid>/comments", methods=["GET","POST"])
def comments(pid):
    p=db.session.get(Post,pid)
    if not p: abort(404)
    if request.method=="POST":
        u=require_user()
        if not u:return jsonify({"error":"Login qiling"}),401
        text=(request.get_json(force=True).get("text") or "").strip()
        if not text:return jsonify({"error":"Bo'sh komment"}),400
        c=Comment(text=text[:500],user_id=u.id,post_id=pid);db.session.add(c);db.session.commit()
    cs=Comment.query.filter_by(post_id=pid).order_by(Comment.created_at.asc()).all()
    return jsonify({"comments":[{"id":c.id,"text":c.text,"user":user_json(c.user),"created_at":c.created_at.isoformat()} for c in cs]})

@app.route("/api/posts/<int:pid>", methods=["DELETE"])
def delete_post(pid):
    u=require_user()
    if not u:return jsonify({"error":"Login qiling"}),401
    p=db.session.get(Post,pid)
    if not p:abort(404)
    if p.user_id!=u.id and not is_admin():return jsonify({"error":"Ruxsat yo'q"}),403
    db.session.delete(p);db.session.commit();return jsonify({"ok":True})

@app.route("/api/posts/<int:pid>/report", methods=["POST"])
def report_post(pid):
    u=require_user()
    if not u:return jsonify({"error":"Login qiling"}),401
    p=db.session.get(Post,pid)
    if not p:abort(404)
    reason=(request.get_json(force=True).get("reason") or "Nomaqbul kontent")[:500]
    db.session.add(Report(reporter_id=u.id,post_id=pid,reason=reason));db.session.commit()
    return jsonify({"ok":True})

@app.route("/api/users/<int:uid>")
def profile(uid):
    viewer=current_user(); target=db.session.get(User,uid)
    if not target:abort(404)
    followed=bool(viewer and target in viewer.following.all())
    posts=Post.query.filter_by(user_id=uid,hidden=False).order_by(Post.created_at.desc()).all()
    return jsonify({"user":user_json(target),"followed":followed,"posts":[post_json(p,viewer) for p in posts]})

@app.route("/api/users/<int:uid>/follow",methods=["POST"])
def follow(uid):
    u=require_user(); target=db.session.get(User,uid)
    if not u or not target:return jsonify({"error":"Topilmadi"}),404
    if target.id==u.id:return jsonify({"error":"O'zingizni follow qila olmaysiz"}),400
    if target in u.following.all():u.following.remove(target);following=False
    else:u.following.append(target);following=True
    db.session.commit();return jsonify({"following":following,"followers":target.followers.count()})

@app.route("/api/profile",methods=["PUT"])
def update_profile():
    u=require_user()
    if not u:return jsonify({"error":"Login qiling"}),401
    d=request.get_json(force=True);u.bio=(d.get("bio") or "")[:300];db.session.commit()
    return jsonify({"user":user_json(u)})

# CHAT / DIRECT MESSAGES
@app.route("/api/users/search")
def search_users():
    u = require_user()
    if not u:
        return jsonify({"error":"Login qiling"}), 401
    q = (request.args.get("q") or "").strip().lower()
    if not q:
        users = User.query.filter(User.id != u.id).order_by(User.first_name.asc()).limit(50).all()
    else:
        users = User.query.filter(
            User.id != u.id,
            db.or_(
                db.func.lower(User.first_name).like(f"%{q}%"),
                db.func.lower(db.func.coalesce(User.username, "")).like(f"%{q}%")
            )
        ).limit(50).all()
    return jsonify({"users":[user_json(x) for x in users]})

@app.route("/api/conversations")
def conversations():
    u = require_user()
    if not u:
        return jsonify({"error":"Login qiling"}), 401

    messages = Message.query.filter(
        db.or_(Message.sender_id == u.id, Message.receiver_id == u.id)
    ).order_by(Message.created_at.desc()).all()

    seen = set()
    out = []
    for m in messages:
        other_id = m.receiver_id if m.sender_id == u.id else m.sender_id
        if other_id in seen:
            continue
        seen.add(other_id)
        other = db.session.get(User, other_id)
        unread = Message.query.filter_by(sender_id=other_id, receiver_id=u.id, is_read=False).count()
        out.append({
            "user": user_json(other),
            "last_message": m.text,
            "created_at": m.created_at.isoformat(),
            "unread": unread
        })
    return jsonify({"conversations":out})

@app.route("/api/messages/<int:uid>", methods=["GET", "POST"])
def messages(uid):
    u = require_user()
    if not u:
        return jsonify({"error":"Login qiling"}), 401

    other = db.session.get(User, uid)
    if not other or other.id == u.id:
        return jsonify({"error":"Foydalanuvchi topilmadi"}), 404

    if request.method == "POST":
        text = (request.get_json(force=True).get("text") or "").strip()
        if not text:
            return jsonify({"error":"Bo'sh xabar yuborib bo'lmaydi"}), 400
        m = Message(sender_id=u.id, receiver_id=other.id, text=text[:2000])
        db.session.add(m)
        db.session.commit()
        return jsonify({"message":{
            "id":m.id, "sender_id":m.sender_id, "receiver_id":m.receiver_id,
            "text":m.text, "created_at":m.created_at.isoformat()
        }})

    Message.query.filter_by(sender_id=other.id, receiver_id=u.id, is_read=False).update(
        {"is_read":True}, synchronize_session=False
    )
    db.session.commit()

    rows = Message.query.filter(
        db.or_(
            db.and_(Message.sender_id == u.id, Message.receiver_id == other.id),
            db.and_(Message.sender_id == other.id, Message.receiver_id == u.id)
        )
    ).order_by(Message.created_at.asc()).all()

    return jsonify({
        "user":user_json(other),
        "messages":[{
            "id":m.id,
            "sender_id":m.sender_id,
            "receiver_id":m.receiver_id,
            "text":m.text,
            "created_at":m.created_at.isoformat()
        } for m in rows]
    })

# ADMIN
def admin_required():
    if not is_admin(): return False
    return True

@app.route("/api/admin/stats")
def admin_stats():
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    return jsonify({"users":User.query.count(),"posts":Post.query.count(),"comments":Comment.query.count(),
                    "reports":Report.query.filter_by(resolved=False).count(),"banned":User.query.filter_by(banned=True).count()})

@app.route("/api/admin/users")
def admin_users():
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    return jsonify({"users":[user_json(u) for u in User.query.order_by(User.created_at.desc()).all()]})

@app.route("/api/admin/users/<int:uid>/ban",methods=["POST"])
def admin_ban(uid):
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    u=db.session.get(User,uid)
    if not u:abort(404)
    u.banned=not u.banned;db.session.commit();return jsonify({"banned":u.banned})

@app.route("/api/admin/users/<int:uid>/verify",methods=["POST"])
def admin_verify(uid):
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    u=db.session.get(User,uid)
    if not u:abort(404)
    u.verified=not u.verified;db.session.commit();return jsonify({"verified":u.verified})

@app.route("/api/admin/posts")
def admin_posts():
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    u=current_user()
    return jsonify({"posts":[post_json(p,u) for p in Post.query.order_by(Post.created_at.desc()).all()]})

@app.route("/api/admin/posts/<int:pid>/hide",methods=["POST"])
def admin_hide(pid):
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    p=db.session.get(Post,pid)
    if not p:abort(404)
    p.hidden=not p.hidden;db.session.commit();return jsonify({"hidden":p.hidden})

@app.route("/api/admin/posts/<int:pid>/pin",methods=["POST"])
def admin_pin(pid):
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    p=db.session.get(Post,pid)
    if not p:abort(404)
    p.pinned=not p.pinned;db.session.commit();return jsonify({"pinned":p.pinned})

@app.route("/api/admin/reports")
def admin_reports():
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    out=[]
    for r in Report.query.filter_by(resolved=False).order_by(Report.created_at.desc()).all():
        out.append({"id":r.id,"reason":r.reason,"post_id":r.post_id,"reporter_id":r.reporter_id,"created_at":r.created_at.isoformat()})
    return jsonify({"reports":out})

@app.route("/api/admin/reports/<int:rid>/resolve",methods=["POST"])
def admin_resolve(rid):
    if not admin_required():return jsonify({"error":"Admin emas"}),403
    r=db.session.get(Report,rid)
    if not r:abort(404)
    r.resolved=True;db.session.commit();return jsonify({"ok":True})

@app.route("/api/admin/announcement",methods=["GET","POST"])
def announcement():
    if request.method=="POST":
        if not admin_required():return jsonify({"error":"Admin emas"}),403
        text=(request.get_json(force=True).get("text") or "")[:1000]
        s=db.session.get(Setting,"announcement") or Setting(key="announcement")
        s.value=text;db.session.add(s);db.session.commit();return jsonify({"ok":True})
    s=db.session.get(Setting,"announcement");return jsonify({"text":s.value if s else ""})

@app.errorhandler(413)
def too_large(e): return jsonify({"error":"Rasm juda katta. Maksimum 10 MB."}),413

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT",5000)))

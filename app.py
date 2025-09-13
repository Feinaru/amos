import os, json, secrets
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
CONTENT_PATH = os.environ.get("CONTENT_PATH", "content.json")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join("static","uploads"))
THUMB_FOLDER = os.environ.get("THUMB_FOLDER", os.path.join(UPLOAD_FOLDER, "thumbs"))
ALLOWED_EXTENSIONS = {"png","jpg","jpeg","webp","gif"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)

def allowed(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS

def load_content():
    if not os.path.exists(CONTENT_PATH):
        default = {
            "site": {
                "brand": "האתר שלי",
                "nav_align": "center",
                "contact_email": "you@example.com",
                "contact_phone": "+972501234567",
                "whatsapp": "+972501234567"
            },
            "sections": [
                {"id": "home", "title": "ברוכים הבאים", "subtitle": "עמוד נחיתה עם גלילה", "bg": "#f5f5f5", "image": ""},
                {"id": "about", "title": "אודות", "subtitle": "כמה מילים עלי/העסק", "bg": "#e8f4ff", "image": ""},
                {"id": "gallery", "title": "גלריה", "subtitle": "עבודות נבחרות", "bg": "#ffffff", "images": []},
                {"id": "services", "title": "שירותים", "subtitle": "מה אני מציע/ה", "bg": "#eefbea", "image": ""},
                {"id": "contact", "title": "צור קשר", "subtitle": "טל׳ / וואטסאפ / מייל", "bg": "#fff1f1", "image": ""}
            ]
        }
        with open(CONTENT_PATH, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
    with open(CONTENT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_content(data):
    with open(CONTENT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def make_square_thumbnail(src_path, dest_path, size=600, bg=(245,245,245)):
    with Image.open(src_path) as im:
        im = im.convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        bg_img = Image.new("RGBA", (size, size), bg + (255,))
        x = (size - im.width) // 2
        y = (size - im.height) // 2
        bg_img.paste(im, (x, y), im)
        rgb = Image.new("RGB", (size, size), bg)
        rgb.paste(bg_img, mask=bg_img.split()[3])
        rgb.save(dest_path, format="JPEG", quality=85, optimize=True)

@app.get("/")
def index():
    data = load_content()
    return render_template("index.html", data=data)

@app.get("/admin/login")
def login_page():
    return render_template("admin_login.html")

@app.post("/admin/login")
def login():
    if request.form.get("password") == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect(url_for("admin"))
    flash("סיסמה שגויה", "error")
    return redirect(url_for("login_page"))

@app.get("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("index"))

@app.get("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("login_page"))
    data = load_content()
    return render_template("admin_dashboard.html", data=data)

@app.post("/admin/save")
def admin_save():
    if not session.get("admin"):
        return redirect(url_for("login_page"))
    data = load_content()

    data["site"]["brand"] = request.form.get("brand", data["site"]["brand"])
    data["site"]["nav_align"] = request.form.get("nav_align", data["site"]["nav_align"])
    data["site"]["contact_email"] = request.form.get("contact_email", data["site"].get("contact_email",""))
    data["site"]["contact_phone"] = request.form.get("contact_phone", data["site"].get("contact_phone",""))
    data["site"]["whatsapp"] = request.form.get("whatsapp", data["site"].get("whatsapp",""))

    for sec in data["sections"]:
        sid = sec["id"]
        if "title" in sec:
            sec["title"] = request.form.get(f"title_{sid}", sec["title"])
        if "subtitle" in sec:
            sec["subtitle"] = request.form.get(f"subtitle_{sid}", sec["subtitle"])
        if "bg" in sec:
            sec["bg"] = request.form.get(f"bg_{sid}", sec["bg"])

        # single background image support for non-gallery sections
        if "image" in sec:
            file = request.files.get(f"image_{sid}")
            if file and file.filename and allowed(file.filename):
                filename = secure_filename(file.filename)
                base, ext = os.path.splitext(filename)
                unique = base + "-" + secrets.token_hex(4) + ext
                path = os.path.join(UPLOAD_FOLDER, unique)
                file.save(path)
                sec["image"] = unique

        # gallery multiple uploads + thumbnails
        if sid == "gallery":
            files = request.files.getlist("gallery_images")
            if files:
                sec.setdefault("images", [])
                for f in files:
                    if f and f.filename and allowed(f.filename):
                        filename = secure_filename(f.filename)
                        base, ext = os.path.splitext(filename)
                        unique = base + "-" + secrets.token_hex(4) + ext
                        full_path = os.path.join(UPLOAD_FOLDER, unique)
                        f.save(full_path)
                        thumb_name = os.path.splitext(unique)[0] + "_thumb.jpg"
                        thumb_path = os.path.join(THUMB_FOLDER, thumb_name)
                        make_square_thumbnail(full_path, thumb_path, size=600, bg=(245,245,245))
                        sec["images"].append({"full": unique, "thumb": thumb_name})

    save_content(data)
    flash("ההגדרות נשמרו בהצלחה", "ok")
    return redirect(url_for("admin"))

@app.post("/admin/delete_image")
def delete_image():
    if not session.get("admin"):
        return redirect(url_for("login_page"))
    img_full = request.form.get("full")  # filename of original
    img_thumb = request.form.get("thumb")  # filename of thumbnail
    data = load_content()
    # remove from content
    for sec in data["sections"]:
        if sec["id"] == "gallery":
            before = len(sec.get("images", []))
            sec["images"] = [x for x in sec.get("images", []) if x.get("full") != img_full]
            after = len(sec["images"])
            # delete files
            if before != after:
                try:
                    if img_full:
                        os.remove(os.path.join(UPLOAD_FOLDER, img_full))
                except FileNotFoundError:
                    pass
                try:
                    if img_thumb:
                        os.remove(os.path.join(THUMB_FOLDER, img_thumb))
                except FileNotFoundError:
                    pass
            break
    save_content(data)
    flash("התמונה נמחקה", "ok")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

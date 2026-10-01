import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, render_template, request

BASE = Path(__file__).parent
UPLOADS = BASE / "static" / "uploads"
RESULTS = BASE / "static" / "results"
UPLOADS.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB tak ki file


def run_script(args):
    """Hamari purani script chalao aur uska JSON output padho."""
    try:
        p = subprocess.run([sys.executable, *args], cwd=BASE,
                           capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": "timeout"}
    out = p.stdout
    start = out.find("{")
    if start == -1:
        return {"ok": False, "reason": "script_error", "detail": (p.stderr or out)[-500:]}
    try:
        return json.JSONDecoder().raw_decode(out[start:])[0]
    except json.JSONDecodeError:
        return {"ok": False, "reason": "bad_output", "detail": out[-500:]}


def save_upload(file, default_ext):
    uid = uuid.uuid4().hex[:8]
    ext = Path(file.filename).suffix.lower() or default_ext
    path = UPLOADS / f"{uid}{ext}"
    file.save(path)
    return uid, path


def get_marker_mm():
    try:
        return str(float(request.form.get("marker_mm", "50")))
    except ValueError:
        return "50.0"


def copy_output(name, uid):
    src = BASE / name
    if not src.exists():
        return None
    dst = RESULTS / f"{uid}_{name}"
    shutil.copy(src, dst)
    return f"results/{dst.name}"


@app.route("/")
def index():
    return render_template("index.html", tab="crack")


@app.route("/inspect", methods=["POST"])
def inspect():
    f = request.files.get("photo")
    if not f or f.filename == "":
        return render_template("index.html", tab="crack", error="Choose a photo first.")
    method = request.form.get("method", "dl")
    uid, photo = save_upload(f, ".jpg")
    result = run_script(["inspect_crack.py", str(
        photo), get_marker_mm(), "--method", method])
    ok = result.get("ok")
    img = copy_output("inspection_result.png", uid) if ok else None
    mask = copy_output("inspection_mask.png", uid) if ok else None
    return render_template("index.html", tab="crack", crack=result, crack_img=img, crack_mask=mask)


@app.route("/vibration", methods=["POST"])
def vibration():
    f = request.files.get("video")
    if not f or f.filename == "":
        return render_template("index.html", tab="vib", error="Choose a video first.")
    uid, video = save_upload(f, ".mp4")
    result = run_script(["vibration.py", str(video), get_marker_mm()])
    img = copy_output("vibration_plot.png", uid) if result.get("ok") else None
    return render_template("index.html", tab="vib", vib=result, vib_img=img)


if __name__ == "__main__":
    # host 0.0.0.0 = same WiFi pe phone se bhi khulegi
    app.run(host="0.0.0.0", port=5000, debug=True)

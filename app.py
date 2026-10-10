import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

BASE = Path(__file__).parent
UPLOADS = BASE / "uploads"          # static/ ke bahar: upload hui file web pe seedhi nahi khulti
RESULTS = BASE / "static" / "results"
MEASURE = BASE / "measurements"     # har upload ka result JSON (agent dobara na naape); web pe nahi dikhta
AGENT_LOGS = BASE / "agent_logs"
for d in (UPLOADS, RESULTS, MEASURE):
    d.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "100"))
KEEP_HOURS = float(os.environ.get("KEEP_FILES_HOURS", "24"))   # isse purani files apne aap hat jaati hain
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

_last_cleanup = 0.0


def cleanup_old_files():
    """KEEP_HOURS se purani uploads, result images, measurement JSON aur agent logs hatao.
    Har upload par chalta hai, lekin 10 minute mein ek hi baar."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < 600:
        return
    _last_cleanup = now
    cutoff = now - KEEP_HOURS * 3600
    for d in (UPLOADS, RESULTS, MEASURE, AGENT_LOGS):
        if not d.is_dir():
            continue
        for f in d.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError:
                pass        # doosre worker ne pehle hi hata di


def run_script(args, uid, outputs=()):
    """Hamari purani script chalao aur uska JSON output padho.
    Har request apne temp folder mein chalti hai (scripts fixed naam se PNG likhti hain,
    to ek saath do users ke results aapas mein na milein). outputs -> static/results/ mein copy.
    Return: (result, {output naam: static ke andar path})"""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            p = subprocess.run([sys.executable, str(BASE / args[0]), *args[1:]], cwd=tmp,
                               capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "timeout"}, {}
        out = p.stdout
        start = out.find("{")
        if start == -1:
            return {"ok": False, "reason": "script_error", "detail": (p.stderr or out)[-500:]}, {}
        try:
            result = json.JSONDecoder().raw_decode(out[start:])[0]
        except json.JSONDecodeError:
            return {"ok": False, "reason": "bad_output", "detail": out[-500:]}, {}

        copied = {}
        for name in outputs if result.get("ok") else ():
            src = Path(tmp) / name
            if src.exists():
                dst = RESULTS / f"{uid}_{name}"
                shutil.copy(src, dst)
                copied[name] = f"results/{dst.name}"
        return result, copied


def save_upload(file, default_ext, allowed):
    """Return: (uid, path), ya (None, None) agar file ka type allowed nahi"""
    ext = Path(file.filename).suffix.lower() or default_ext
    if ext not in allowed:
        return None, None
    uid = uuid.uuid4().hex[:8]
    path = UPLOADS / f"{uid}{ext}"
    file.save(path)
    return uid, path


def get_marker_mm():
    try:
        return str(float(request.form.get("marker_mm", "50")))
    except ValueError:
        return "50.0"


def save_measurement(uid, path, result, method=None):
    """Result yaad rakho taaki /report wala agent wahi use kare."""
    data = {"file": path.relative_to(BASE).as_posix(), "marker_mm": float(get_marker_mm()),
            "method": method, "result": result}
    (MEASURE / f"{uid}.json").write_text(json.dumps(data), encoding="utf-8")


@app.route("/health")
def health():
    """Load balancer / App Runner health check"""
    return "ok", 200, {"Content-Type": "text/plain"}


@app.errorhandler(RequestEntityTooLarge)
def too_large(e):
    tab = "vib" if request.path == "/vibration" else "crack"
    return render_template("index.html", tab=tab,
                           error=f"File is too large. The limit is {MAX_UPLOAD_MB} MB."), 413


@app.route("/")
def index():
    return render_template("index.html", tab="crack")


@app.route("/inspect", methods=["POST"])
def inspect():
    f = request.files.get("photo")
    if not f or f.filename == "":
        return render_template("index.html", tab="crack", error="Choose a photo first.")
    cleanup_old_files()
    method = request.form.get("method", "dl")
    if method not in ("dl", "classical"):
        method = "dl"
    uid, photo = save_upload(f, ".jpg", PHOTO_EXTS)
    if uid is None:
        return render_template("index.html", tab="crack",
                               error="Upload a photo (JPG, PNG, BMP, WEBP or TIFF).")
    result, out = run_script(["inspect_crack.py", str(photo), get_marker_mm(), "--method", method],
                             uid, ["inspection_result.png", "inspection_mask.png"])
    save_measurement(uid, photo, result, method)
    return render_template("index.html", tab="crack", crack=result,
                           crack_img=out.get("inspection_result.png"),
                           crack_mask=out.get("inspection_mask.png"),
                           uid=uid, marker_mm=get_marker_mm(), method=method)


@app.route("/vibration", methods=["POST"])
def vibration():
    f = request.files.get("video")
    if not f or f.filename == "":
        return render_template("index.html", tab="vib", error="Choose a video first.")
    cleanup_old_files()
    uid, video = save_upload(f, ".mp4", VIDEO_EXTS)
    if uid is None:
        return render_template("index.html", tab="vib",
                               error="Upload a video (MP4, MOV, AVI, MKV or WEBM).")
    result, out = run_script(["vibration.py", str(video), get_marker_mm()], uid, ["vibration_plot.png"])
    save_measurement(uid, video, result)
    return render_template("index.html", tab="vib", vib=result, vib_img=out.get("vibration_plot.png"),
                           uid=uid, marker_mm=get_marker_mm())


@app.route("/report", methods=["POST"])
def report():
    """Pehle upload hui photo/video par agent.py chalao, report + steps JSON mein lautao."""
    kind = request.form.get("kind")
    uid = request.form.get("uid", "")
    if kind not in ("crack", "vib") or not re.fullmatch(r"[0-9a-f]{8}", uid):
        return jsonify(ok=False, error="Bad request."), 400
    files = list(UPLOADS.glob(f"{uid}.*"))
    if not files:
        return jsonify(ok=False, error="The uploaded file is no longer available. Upload it again."), 404

    # relative path: report mein server ka poora folder path na dikhe
    args = [str(BASE / "agent.py"), "--photo" if kind == "crack" else "--video",
            files[0].relative_to(BASE).as_posix(),
            "--marker-mm", get_marker_mm()]
    if kind == "crack":
        method = request.form.get("method", "dl")
        args += ["--method", method if method in ("dl", "classical") else "dl"]
    saved = MEASURE / f"{uid}.json"
    if saved.exists():          # pehle ka result -> agent dobara nahi naapega
        args += ["--crack-json" if kind == "crack" else "--vib-json", str(saved)]
    try:
        # stdin band: agent ka "naya file do" wala sawaal yahan skip ho jaata hai
        p = subprocess.run([sys.executable, *args], cwd=BASE, capture_output=True, text=True,
                           timeout=600, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return jsonify(ok=False, error="The report took too long. Try again."), 504
    m = re.search(r"^Log: (.+\.json)\s*$", p.stdout, re.M)
    if not m:
        return jsonify(ok=False, error="The agent stopped with an error."), 500
    log = json.loads((BASE / m.group(1).strip()).read_text(encoding="utf-8"))

    steps = []
    for s in log["steps"]:
        if s["type"] == "tool":
            out = s["output"]
            steps.append({"kind": "tool", "name": s["tool"], "seconds": s["seconds"],
                          "ok": bool(out.get("ok")), "reason": out.get("reason"),
                          "reused": bool(s.get("reused"))})
        elif s["type"] == "llm":
            steps.append({"kind": "llm", "name": log.get("model"), "seconds": s["seconds"],
                          "tokens": s["tokens"], "stop": s["stop_reason"]})
        elif s["type"] == "fallback":
            steps.append({"kind": "fallback", "reason": s["reason"].split(":")[0]})
    return jsonify(ok=True, report=log["report"], offline=log["mode"] != "bedrock",
                   model=log.get("model"), mode=log["mode"], steps=steps,
                   total_seconds=log["total_seconds"], tokens=log["total_tokens"])


if __name__ == "__main__":
    # host 0.0.0.0 = same WiFi pe phone se bhi khulegi
    app.run(host="0.0.0.0", port=5000, debug=True)

import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request

BASE = Path(__file__).parent
UPLOADS = BASE / "static" / "uploads"
RESULTS = BASE / "static" / "results"
MEASURE = BASE / "measurements"     # har upload ka result JSON (agent dobara na naape); web pe nahi dikhta
for d in (UPLOADS, RESULTS, MEASURE):
    d.mkdir(parents=True, exist_ok=True)

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


def save_measurement(uid, path, result, method=None):
    """Result yaad rakho taaki /report wala agent wahi use kare."""
    data = {"file": path.relative_to(BASE).as_posix(), "marker_mm": float(get_marker_mm()),
            "method": method, "result": result}
    (MEASURE / f"{uid}.json").write_text(json.dumps(data), encoding="utf-8")


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
    save_measurement(uid, photo, result, method)
    ok = result.get("ok")
    img = copy_output("inspection_result.png", uid) if ok else None
    mask = copy_output("inspection_mask.png", uid) if ok else None
    return render_template("index.html", tab="crack", crack=result, crack_img=img, crack_mask=mask,
                           uid=uid, marker_mm=get_marker_mm(), method=method)


@app.route("/vibration", methods=["POST"])
def vibration():
    f = request.files.get("video")
    if not f or f.filename == "":
        return render_template("index.html", tab="vib", error="Choose a video first.")
    uid, video = save_upload(f, ".mp4")
    result = run_script(["vibration.py", str(video), get_marker_mm()])
    save_measurement(uid, video, result)
    img = copy_output("vibration_plot.png", uid) if result.get("ok") else None
    return render_template("index.html", tab="vib", vib=result, vib_img=img,
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

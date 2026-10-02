# agent.py - CrackPulse AI agent: photo/video lo, tools chalao, draft inspection report likho
# Dimaag: Amazon Bedrock Converse API (tool use). --offline = simple rules, bina AI ke.
# Chalao:
#   python agent.py --photo test_tilted.png --video test_vibration.mp4 --marker-mm 50
#   python agent.py --photo wall.jpg --offline
# Auth: AWS_BEARER_TOKEN_BEDROCK environment variable (boto3 khud padhta hai; hum kabhi print/save nahi karte)
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
LOG_DIR = BASE / "agent_logs"
REGION = "ap-southeast-2"
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "au.anthropic.claude-haiku-4-5-20251001-v1:0")
MAX_TOOL_STEPS = 6
MAX_LLM_TURNS = 8
MAX_TOKENS = 900
DRAFT_LINE = "DRAFT - needs review by a qualified engineer"

GUIDANCE = {
    ("inspect_crack", "marker_not_found"):
        "Photo dobara lo: poora marker frame mein ho, saaf/sharp ho, us par chamak (glare) na ho, "
        "aur crack marker ke paas ho.",
    ("measure_vibration", "marker_not_found"):
        "Video dobara banao: marker har frame mein poora dikhe, camera hile nahi (tripod ya deewar "
        "se tika kar), aur roshni achhi ho.",
    ("measure_vibration", "video_not_opened"):
        "Video file khul nahi rahi. MP4 format mein dobara save/record karo.",
    ("*", "timeout"): "Tool bahut der tak chala. Chhoti photo/video ke saath dobara try karo.",
    ("*", "file_not_found"): "File nahi mili. Path check karo.",
}

SYSTEM = f"""You are CrackPulse's inspection assistant. You prepare a DRAFT inspection note from measurements made by two tools.

Tools:
- inspect_crack: measures crack width and length from a photo that contains a printed ArUco marker.
- measure_vibration: measures the dominant vibration frequency and amplitude from a video of a marker.

Run the tool that matches each file the user gives (photo -> inspect_crack, video -> measure_vibration), using the marker size the user states. Call each tool once; call it again only if a result tells you a new file was provided.

Report rules:
- The first line must be exactly: {DRAFT_LINE}
- Use only numbers that appear in tool results or in the user's message. Never estimate, convert, or invent numbers. If something was not measured, say so.
- Never conclude that the structure is safe, unsafe, or fit for use. You may say what the measured category usually calls for (for example monitoring), and you must recommend review by a qualified structural engineer.
- If a tool failed, say that no measurement was made and tell the user what to do, using the tool's "guidance" text.
- Sections: Inputs, Crack measurement, Vibration measurement, Observations, Recommended next steps, Limitations. Write "Not provided" for a section with no file.
- Plain text, under 300 words."""

TOOLS = [
    {"toolSpec": {
        "name": "inspect_crack",
        "description": "Measure crack width (median and 95th-percentile max, mm), length (mm) and BRE Digest 251 "
                       "damage category from a photo containing an ArUco marker of known size.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "photo": {"type": "string", "description": "Photo path exactly as given by the user"},
                "marker_mm": {"type": "number", "description": "Side of the black marker square in mm"},
                "method": {"type": "string", "enum": ["dl", "classical"],
                           "description": "dl = trained U-Net (default), classical = image processing"},
            },
            "required": ["photo", "marker_mm"],
        }},
    }},
    {"toolSpec": {
        "name": "measure_vibration",
        "description": "Measure dominant vibration frequency (Hz) and amplitude (mm) of an ArUco marker in a video.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {
                "video": {"type": "string", "description": "Video path exactly as given by the user"},
                "marker_mm": {"type": "number", "description": "Side of the black marker square in mm"},
            },
            "required": ["video", "marker_mm"],
        }},
    }},
]


class Agent:
    def __init__(self, photo, video, marker_mm, method, mode):
        self.files = {"photo": photo, "video": video}
        self.allowed = {str(p) for p in (photo, video) if p}
        self.marker_mm, self.method, self.mode = marker_mm, method, mode
        self.steps, self.results, self.retried = [], {}, set()
        self.tool_steps = 0
        self.t0 = time.time()

    # ---------- logging ----------
    def log(self, **step):
        step["step"] = len(self.steps) + 1
        self.steps.append(step)

    # ---------- tools: purani scripts ko hi chalao ----------
    def _run_script(self, args):
        try:
            p = subprocess.run([sys.executable, *args], cwd=BASE, capture_output=True,
                               text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return {"ok": False, "reason": "timeout"}
        out = p.stdout
        start = out.find("{")
        if start == -1:
            return {"ok": False, "reason": "script_error", "detail": (p.stderr or out)[-300:]}
        try:
            return json.JSONDecoder().raw_decode(out[start:])[0]
        except json.JSONDecodeError:
            return {"ok": False, "reason": "bad_output", "detail": out[-300:]}

    def _call(self, name, inp):
        key = "photo" if name == "inspect_crack" else "video"
        path = str(inp.get(key, ""))
        if path not in self.allowed:
            return {"ok": False, "reason": "file_not_allowed",
                    "detail": f"Only files given by the user can be used: {sorted(self.allowed)}"}
        if not Path(path).exists():
            return {"ok": False, "reason": "file_not_found"}
        mm = str(float(inp.get("marker_mm", self.marker_mm)))
        if name == "inspect_crack":
            method = inp.get("method", self.method)
            if method not in ("dl", "classical"):
                method = self.method
            return self._run_script(["inspect_crack.py", path, mm, "--method", method])
        return self._run_script(["vibration.py", path, mm])

    def run_tool(self, name, inp):
        """Tool chalao, log karo; fail ho to user ko batao aur ek baar naya file maango."""
        if name not in ("inspect_crack", "measure_vibration"):
            return {"ok": False, "reason": "unknown_tool"}
        if self.tool_steps >= MAX_TOOL_STEPS:
            return {"ok": False, "reason": "step_limit",
                    "detail": "Tool step limit reached. Write the report with the results you have."}
        self.tool_steps += 1
        t = time.time()
        res = self._call(name, inp)
        self.log(type="tool", tool=name, input=inp, output=res, seconds=round(time.time() - t, 2))

        if not res.get("ok"):
            reason = res.get("reason", "")
            res["guidance"] = (GUIDANCE.get((name, reason)) or GUIDANCE.get(("*", reason))
                               or "Input check karo aur dobara try karo.")
            new = self.ask_retry(name, res)
            if new:
                key = "photo" if name == "inspect_crack" else "video"
                self.allowed.add(new)
                self.files[key] = new
                res = self.run_tool(name, {**inp, key: new})
                res["note"] = f"First attempt failed ({reason}); user provided a new file: {new}"
        self.results[name] = res
        return res

    def ask_retry(self, name, res):
        if name in self.retried or res.get("reason") == "step_limit":
            return None
        self.retried.add(name)
        print(f"\n[!] {name} fail hua: {res.get('reason')}")
        print(f"    {res['guidance']}")
        try:
            new = input("    Naya file path do (Enter = skip): ").strip().strip('"')
        except EOFError:
            return None
        return new or None

    # ---------- Bedrock (AI) mode ----------
    def run_bedrock(self):
        import boto3
        from botocore.config import Config

        client = boto3.client("bedrock-runtime", region_name=REGION,
                              config=Config(retries={"max_attempts": 3}, read_timeout=120))
        given = [f"{k}: {v}" for k, v in self.files.items() if v]
        msg = (f"Files: {'; '.join(given)}. Marker size: {self.marker_mm} mm. "
               f"Crack method: {self.method}. Run the right tools and write the draft inspection report.")
        messages = [{"role": "user", "content": [{"text": msg}]}]

        for _ in range(MAX_LLM_TURNS):
            t = time.time()
            resp = client.converse(modelId=MODEL_ID, system=[{"text": SYSTEM}], messages=messages,
                                   toolConfig={"tools": TOOLS},
                                   inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0})
            out_msg = resp["output"]["message"]
            usage = resp.get("usage", {})
            uses = [c["toolUse"] for c in out_msg["content"] if "toolUse" in c]
            self.log(type="llm", model=MODEL_ID, stop_reason=resp.get("stopReason"),
                     tool_requests=[{"tool": u["name"], "input": u["input"]} for u in uses],
                     seconds=round(time.time() - t, 2),
                     tokens={"input": usage.get("inputTokens"), "output": usage.get("outputTokens")})
            messages.append(out_msg)

            if resp.get("stopReason") != "tool_use":
                text = "\n".join(c["text"] for c in out_msg["content"] if "text" in c).strip()
                if resp.get("stopReason") == "max_tokens":
                    text += "\n\n[Report was cut off at the token limit.]"
                return text

            results = []
            for u in uses:
                res = self.run_tool(u["name"], u["input"])
                results.append({"toolResult": {
                    "toolUseId": u["toolUseId"], "content": [{"json": res}],
                    "status": "success" if res.get("ok") else "error"}})
            messages.append({"role": "user", "content": results})
        raise RuntimeError("LLM turn limit reached without a final report")

    # ---------- offline mode: simple rules ----------
    def run_offline(self):
        if self.files["photo"] and "inspect_crack" not in self.results:
            self.run_tool("inspect_crack", {"photo": self.files["photo"],
                                            "marker_mm": self.marker_mm, "method": self.method})
        if self.files["video"] and "measure_vibration" not in self.results:
            self.run_tool("measure_vibration", {"video": self.files["video"], "marker_mm": self.marker_mm})
        return offline_report(self.files, self.marker_mm, self.results)

    # ---------- main ----------
    def run(self):
        report, fallback_reason = None, None
        if self.mode == "bedrock":
            try:
                report = self.run_bedrock()
            except Exception as e:      # koi bhi Bedrock/network error -> rules wala fallback
                fallback_reason = f"{type(e).__name__}: {e}"
                self.log(type="fallback", reason=fallback_reason)
        if report is None:
            report = self.run_offline()
            if fallback_reason:
                report += "\n\n[AI service unavailable; report generated by offline rules.]"
        report = finalize(report, self.marker_mm, self.results)
        path = self.save_log(report, fallback_reason)
        return report, path

    def save_log(self, report, fallback_reason):
        LOG_DIR.mkdir(exist_ok=True)
        llm = [s for s in self.steps if s["type"] == "llm"]
        data = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "mode": self.mode if not fallback_reason else "bedrock->offline_fallback",
            "model": MODEL_ID if self.mode == "bedrock" else None,
            "region": REGION if self.mode == "bedrock" else None,
            "inputs": {**self.files, "marker_mm": self.marker_mm, "method": self.method},
            "tool_steps": self.tool_steps,
            "total_seconds": round(time.time() - self.t0, 2),
            "total_tokens": {"input": sum(s["tokens"]["input"] or 0 for s in llm),
                             "output": sum(s["tokens"]["output"] or 0 for s in llm)},
            "steps": self.steps,
            "report": report,
        }
        path = LOG_DIR / f"agent_{datetime.now():%Y%m%d_%H%M%S}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path


def offline_report(files, marker_mm, results):
    L = [DRAFT_LINE, "", "Inputs"]
    L += [f"- {k.capitalize()}: {v}" for k, v in files.items() if v]
    L.append(f"- Marker size: {marker_mm} mm")
    steps = []

    L += ["", "Crack measurement"]
    c = results.get("inspect_crack")
    if not files["photo"]:
        L.append("Not provided.")
    elif not c or not c.get("ok"):
        L.append(f"No measurement made ({(c or {}).get('reason', 'not run')}).")
        if c and c.get("guidance"):
            steps.append(c["guidance"])
    elif not c.get("crack_found"):
        L.append("No crack was detected in the photo.")
    else:
        L += [f"- Method: {c['method']}",
              f"- Width: median {c['width_median_mm']} mm, max (95th percentile) {c['width_max_mm']} mm",
              f"- Length: {c['length_mm']} mm",
              f"- BRE Digest 251 category: {c['bre_category']} ({c['bre_label']})"]
        cat = c["bre_category"]
        if cat <= 1:
            steps.append("Category 0-1 is usually treated as cosmetic. Record it and re-measure to see "
                         "whether the width changes over time.")
        elif cat == 2:
            steps.append("Category 2 usually calls for monitoring. Re-measure with the same marker at regular "
                         "intervals and compare widths.")
        else:
            steps.append("Category 3 or higher usually calls for prompt assessment. Arrange an inspection by "
                         "a qualified structural engineer soon.")

    L += ["", "Vibration measurement"]
    v = results.get("measure_vibration")
    if not files["video"]:
        L.append("Not provided.")
    elif not v or not v.get("ok"):
        L.append(f"No measurement made ({(v or {}).get('reason', 'not run')}).")
        if v and v.get("guidance"):
            steps.append(v["guidance"])
    else:
        L += [f"- Dominant frequency: {v['frequency_hz']} Hz ({v['main_axis']} axis)",
              f"- Amplitude: {v['amplitude_mm']} mm",
              f"- Video: {v['frames']} frames at {v['fps']} fps, marker found in {v['marker_found_frames']}"]
        steps.append("Compare the measured frequency with the structure's expected natural frequency and "
                     "with earlier recordings; a shift can indicate a change worth investigating.")

    steps.append("Have a qualified structural engineer review these results before any decision.")
    L += ["", "Recommended next steps"] + [f"- {s}" for s in steps]
    L += ["", "Limitations",
          "- Automated measurement from a single photo/video; accuracy depends on focus, lighting, marker "
          "print size and camera angle.",
          "- This draft does not assess structural safety."]
    return "\n".join(L)


def _numbers(obj):
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in _numbers(v)]
    if isinstance(obj, list):
        return [n for v in obj for n in _numbers(v)]
    return []


def finalize(report, marker_mm, results):
    """Upar DRAFT line pakki karo, aur mm/Hz wale har number ko tool output se milao."""
    if not report.lstrip().startswith(DRAFT_LINE):
        report = DRAFT_LINE + "\n\n" + report
    known = _numbers(results) + [float(marker_mm)]
    bad = []
    for num, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(mm|Hz)\b", report):
        x = float(num)
        if not any(abs(x - k) <= max(0.005, 0.01 * abs(k)) for k in known):
            bad.append(f"{num} {unit}")
    if bad:
        report += ("\n\n[Check: these values were not found in tool outputs and must be verified: "
                   + ", ".join(sorted(set(bad))) + "]")
    return report


def main():
    ap = argparse.ArgumentParser(description="CrackPulse inspection agent")
    ap.add_argument("--photo", help="crack photo (ArUco marker ke saath)")
    ap.add_argument("--video", help="vibration video (ArUco marker ke saath)")
    ap.add_argument("--marker-mm", type=float, default=50.0)
    ap.add_argument("--method", choices=["dl", "classical"], default="dl")
    ap.add_argument("--offline", action="store_true", help="Bedrock ke bina, simple rules se report")
    a = ap.parse_args()
    if not a.photo and not a.video:
        ap.error("--photo ya --video (ya dono) do")

    agent = Agent(a.photo, a.video, a.marker_mm, a.method, "offline" if a.offline else "bedrock")
    report, log_path = agent.run()
    print("\n" + "=" * 60 + "\n" + report + "\n" + "=" * 60)
    print(f"Log: {log_path.relative_to(BASE)}")


if __name__ == "__main__":
    main()

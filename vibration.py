import argparse
import json
import cv2
import numpy as np


def track_marker(video_path):
    """Har frame mein marker ka center (x, y) aur size (px) nikaalo."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    params = cv2.aruco.DetectorParameters()
    # pixel se bhi chhota hilna pakadne ke liye
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(dictionary, params)

    xs, ys, sides = [], [], []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)
        if ids is None:
            xs.append(np.nan)
            ys.append(np.nan)
            continue
        c = corners[0].reshape(4, 2)
        xs.append(c[:, 0].mean())
        ys.append(c[:, 1].mean())
        sides.append(
            np.mean([np.linalg.norm(c[i] - c[(i + 1) % 4]) for i in range(4)]))
    cap.release()
    return np.array(xs), np.array(ys), np.array(sides), fps


def fill_gaps(a):
    """Jin frames mein marker nahi mila, unko aas-paas ke frames se bhar do."""
    idx = np.arange(len(a))
    good = ~np.isnan(a)
    return np.interp(idx, idx[good], a[good])


def dominant(signal_mm, fps):
    """FFT se sabse strong frequency (Hz) aur uska amplitude (mm) nikaalo."""
    s = signal_mm - signal_mm.mean()
    w = np.hanning(len(s))
    spec = np.abs(np.fft.rfft(s * w))
    freqs = np.fft.rfftfreq(len(s), 1.0 / fps)
    spec[0] = 0
    k = int(np.argmax(spec))
    amp = 2 * spec[k] / w.sum()
    return float(freqs[k]), float(amp)


def save_plot(sig, path):
    """Hilne ka graph OpenCV se banao: dark green background, gold wave."""
    W, H = 900, 300
    # website ka dark green (BGR)
    img = np.full((H, W, 3), (18, 24, 8), np.uint8)
    s = sig - sig.mean()
    m = np.abs(s).max() or 1
    pts = np.array([[int(i * (W - 1) / (len(s) - 1)), int(H / 2 - s[i] / m * (H / 2 - 20))]
                    for i in range(len(s))], np.int32)
    cv2.line(img, (0, H // 2), (W, H // 2), (60, 80, 50),
             1)            # beech ki halki line
    cv2.polylines(img, [pts], False, (106, 196, 233),
                  2, cv2.LINE_AA)   # gold wave
    cv2.imwrite(path, img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("marker_mm", nargs="?", type=float, default=50.0)
    args = ap.parse_args()

    res = track_marker(args.video)
    if res is None:
        print(json.dumps(
            {"ok": False, "reason": "video_not_opened"}, indent=2))
        return
    xs, ys, sides, fps = res
    found = int(np.sum(~np.isnan(ys)))
    if len(ys) == 0 or found < 0.5 * len(ys):
        print(json.dumps({"ok": False, "reason": "marker_not_found",
                          "frames": len(ys), "found": found}, indent=2))
        return

    mm_per_px = args.marker_mm / float(np.median(sides))
    x_mm = fill_gaps(xs) * mm_per_px
    y_mm = fill_gaps(ys) * mm_per_px

    fx, ax_ = dominant(x_mm, fps)
    fy, ay = dominant(y_mm, fps)
    if ay >= ax_:
        axis, freq, amp, sig = "vertical", fy, ay, y_mm
    else:
        axis, freq, amp, sig = "horizontal", fx, ax_, x_mm

    save_plot(sig, "vibration_plot.png")
    print(json.dumps({
        "ok": True,
        "video": args.video,
        "fps": round(fps, 2),
        "frames": len(ys),
        "marker_found_frames": found,
        "mm_per_px": round(mm_per_px, 4),
        "main_axis": axis,
        "frequency_hz": round(freq, 2),
        "amplitude_mm": round(amp, 3),
    }, indent=2))


if __name__ == "__main__":
    main()

# inspect_crack.py - poora pipeline: photo -> marker se scale -> crack dhoondho -> width/length -> report
# Chalao:  python inspect_crack.py photo.jpg  [marker_mm]
import sys, json
import cv2
import numpy as np
from skimage.morphology import skeletonize
from aruco_scale import rectify_with_marker, _DETECTOR

PPM = 10.0   # rectified image mein 1 mm = 10 px


def bre_category(w_mm):
    """BRE Digest 251 (deewar ke cracks ki damage category, width ke hisaab se)"""
    if w_mm < 0.1:  return 0, "Negligible (hairline)"
    if w_mm <= 1:   return 1, "Very slight"
    if w_mm <= 5:   return 2, "Slight"
    if w_mm <= 15:  return 3, "Moderate"
    if w_mm <= 25:  return 4, "Severe"
    return 5, "Very severe"


_SEG = None


def raw_mask(img, method):
    if method == "dl":
        global _SEG
        if _SEG is None:
            from crack_model import CrackSegmenter
            _SEG = CrackSegmenter("crack_unet.onnx")
        prob = _SEG.predict(img)
        return ((prob > 0.5) * 255).astype(np.uint8)
    # classical: blackhat patli andheri lakeerein ubhaarta hai, Otsu threshold khud chunta hai
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    bh = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k)
    return cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def find_crack_mask(img, method="classical"):
    mask = raw_mask(img, method)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # marker ko mask se hata do (warna woh bhi "crack" lagega)
    corners, ids, _ = _DETECTOR.detectMarkers(gray)
    if ids is not None:
        for c in corners:
            x, y, w, h = cv2.boundingRect(c.reshape(4, 2).astype(np.int32))
            pad = int(0.25 * max(w, h))
            cv2.rectangle(mask, (x - pad, y - pad), (x + w + pad, y + h + pad), 0, -1)

    # sirf lambe-patle tukde rakho (crack), gol dhabbe/daag hatao
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    clean = np.zeros_like(mask)
    for i in range(1, n):
        w, h, area = st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT], st[i, cv2.CC_STAT_AREA]
        length = max(w, h)
        if length >= 15 * PPM and area / (length + 1e-6) < length / 3:
            clean[lab == i] = 255
    return clean


def subpixel_widths(gray, mask, skel, dist, step=0.25):
    """Har skeleton point par crack ke aar-paar (normal direction mein) brightness profile lo.
    Width = dono kinaron ke beech ki doori jahan andhera aadha ho jaata hai (FWHM),
    linear interpolation se -> pixel se barik. Mask sirf crack dhoondhta hai, width gray se aati hai.
    Profile kharab ho (kam contrast / kinara na mile) to purani distance-transform width rehti hai."""
    ys, xs = np.nonzero(skel)
    d = dist[ys, xs]
    widths = d * 2 / PPM
    if len(ys) == 0:
        return widths

    # normal direction: smooth mask ke gradient ka structure tensor
    m = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), 2)
    gx, gy = cv2.Sobel(m, cv2.CV_32F, 1, 0), cv2.Sobel(m, cv2.CV_32F, 0, 1)
    jxx, jxy, jyy = (cv2.GaussianBlur(a, (0, 0), 3) for a in (gx * gx, gx * gy, gy * gy))
    th = 0.5 * np.arctan2(2 * jxy[ys, xs], jxx[ys, xs] - jyy[ys, xs])
    nx, ny = np.cos(th), np.sin(th)

    g = gray.astype(np.float32)
    t = np.arange(-(2 * d.max() + 6), 2 * d.max() + 6 + step / 2, step, dtype=np.float32)
    at, idx = np.abs(t)[None], np.arange(len(t))[None]
    for s in range(0, len(ys), 5000):                # remap ki 32767 rows ki limit, aur memory
        sl = slice(s, s + 5000)
        mx = (xs[sl, None] + nx[sl, None] * t).astype(np.float32)
        my = (ys[sl, None] + ny[sl, None] * t).astype(np.float32)
        p = cv2.remap(g, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

        r = (2 * d[sl] + 4)[:, None]                  # crack ke bahar kitni door tak dekhna hai
        bg = np.nanmedian(np.where((at > r) & (at <= r + 2), p, np.nan), axis=1)
        inner = np.where(at <= np.maximum(d[sl], 1)[:, None], p, np.inf)
        c = np.argmin(inner, axis=1)
        rows = np.arange(len(c))
        core = inner[rows, c]
        half = (bg + core) / 2

        # c se baayein aur daayein pehla point jo aadhe se zyada roshan hai
        above = (p >= half[:, None]) & (at <= r)
        i = np.where(above & (idx < c[:, None]), idx, -1).max(axis=1)
        j = np.where(above & (idx > c[:, None]), idx, len(t)).min(axis=1)
        ok = (bg - core >= 10) & (i >= 0) & (j < len(t))
        i, j = np.clip(i, 0, len(t) - 2), np.clip(j, 1, len(t) - 1)
        with np.errstate(divide="ignore", invalid="ignore"):
            xl = t[i] + (half - p[rows, i]) / (p[rows, i + 1] - p[rows, i]) * step
            xr = t[j - 1] + (half - p[rows, j - 1]) / (p[rows, j] - p[rows, j - 1]) * step
            w = widths[sl]
            w[ok] = (xr - xl)[ok] / PPM
    return widths


def measure(mask, gray=None):
    skel = skeletonize(mask > 0)
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    # gray mile to sub-pixel width, warna purana tarika (0.2 mm ke steps mein)
    widths = subpixel_widths(gray, mask, skel, dist) if gray is not None else dist[skel] * 2 / PPM
    # length: skeleton ki har shaakh ka contour lo; patli line ka contour
    # dono taraf se ghoomta hai, isliye arcLength / 2 = asli lambai
    cnts, _ = cv2.findContours(skel.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    # approxPolyDP pixel ki seedhi-tedhi "seedhiyon" ko smooth karta hai
    length_mm = sum(cv2.arcLength(cv2.approxPolyDP(c, 1.5, True), True) for c in cnts) / 2 / PPM
    return skel, dist, widths, length_mm


def draw(img, skel, dist, widths):
    out = img.copy()
    if len(widths) == 0:
        return out
    wmax = max(np.percentile(widths, 95), 0.5)
    ys, xs = np.nonzero(skel)                               # widths isi order mein hain
    for y, x, w in zip(ys, xs, widths):
        t = min(w / wmax, 1.0)                              # 0 = patla, 1 = chauda
        color = (0, int(255 * (1 - t)), int(255 * t))      # hara -> laal
        cv2.circle(out, (int(x), int(y)), 2, color, -1)
    return out


def inspect(path, marker_mm=50.0, method="classical"):
    img = cv2.imread(path)
    if img is None:
        return {"ok": False, "reason": f"photo nahi khuli: {path}"}
    warped, _ = rectify_with_marker(img, marker_mm=marker_mm, px_per_mm=PPM)
    if warped is None:
        return {"ok": False, "reason": "marker_not_found"}

    mask = find_crack_mask(warped, method)
    skel, dist, widths, length_mm = measure(mask, cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY))
    if len(widths) == 0:
        return {"ok": True, "crack_found": False}

    w_med = float(np.median(widths))
    w_max = float(np.percentile(widths, 95))      # 95th percentile = "max" (noise se bachne ke liye)
    cat, label = bre_category(w_max)

    out = draw(warped, skel, dist, widths)
    txt = f"max {w_max:.2f} mm | median {w_med:.2f} mm | length {length_mm:.0f} mm | BRE {cat}: {label}"
    cv2.rectangle(out, (0, 0), (out.shape[1], 50), (255, 255, 255), -1)
    cv2.putText(out, txt, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.imwrite("inspection_result.png", out)
    cv2.imwrite("inspection_mask.png", mask)

    return {"ok": True, "crack_found": True, "image": path, "method": method,
            "width_median_mm": round(w_med, 2), "width_max_mm": round(w_max, 2),
            "length_mm": round(length_mm, 1), "bre_category": cat, "bre_label": label}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", nargs="?", default="test_tilted.png")
    ap.add_argument("marker_mm", nargs="?", type=float, default=50.0)
    ap.add_argument("--method", choices=["classical", "dl"], default="classical",
                    help="dl = trained U-Net model (crack_unet.onnx chahiye)")
    a = ap.parse_args()
    result = inspect(a.photo, a.marker_mm, a.method)
    print(json.dumps(result, indent=2))
    with open("inspection_result.json", "w") as f:
        json.dump(result, f, indent=2)

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


def find_crack_mask(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # blackhat: patli andheri lakeerein (cracks) ubhar kar aati hain
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    bh = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k)
    # fixed number ki jagah Otsu: har photo ke liye threshold khud chunega
    _, mask = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # marker ko mask se hata do (warna woh bhi "crack" lagega)
    corners, ids, _ = _DETECTOR.detectMarkers(gray)
    if ids is not None:
        for c in corners:
            pts = c.reshape(4, 2).astype(np.int32)
            x, y, w, h = cv2.boundingRect(pts)
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


def measure(mask):
    skel = skeletonize(mask > 0)
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    widths = dist[skel] * 2 / PPM
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
    ys, xs = np.nonzero(skel)
    for y, x in zip(ys, xs):
        t = min(dist[y, x] * 2 / PPM / wmax, 1.0)          # 0 = patla, 1 = chauda
        color = (0, int(255 * (1 - t)), int(255 * t))      # hara -> laal
        cv2.circle(out, (int(x), int(y)), 2, color, -1)
    return out


def inspect(path, marker_mm=50.0):
    img = cv2.imread(path)
    if img is None:
        return {"ok": False, "reason": f"photo nahi khuli: {path}"}
    warped, _ = rectify_with_marker(img, marker_mm=marker_mm, px_per_mm=PPM)
    if warped is None:
        return {"ok": False, "reason": "marker_not_found"}

    mask = find_crack_mask(warped)
    skel, dist, widths, length_mm = measure(mask)
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

    return {"ok": True, "crack_found": True, "image": path,
            "width_median_mm": round(w_med, 2), "width_max_mm": round(w_max, 2),
            "length_mm": round(length_mm, 1), "bre_category": cat, "bre_label": label}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "test_tilted.png"
    mm = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    result = inspect(path, mm)
    print(json.dumps(result, indent=2))
    with open("inspection_result.json", "w") as f:
        json.dump(result, f, indent=2)

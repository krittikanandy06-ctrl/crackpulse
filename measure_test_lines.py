# measure_test_lines.py - calibration sheet ki photo se 4 test lines (0.3 / 0.5 / 1.0 / 2.0 mm) ki width naapo
# Classical aur DL dono method, asli width se compare karke % galti batata hai.
# Chalao:  python measure_test_lines.py photo.jpg 50      (50 = marker ka kaala square, mm mein)
#          python measure_test_lines.py photos_folder 50  (folder ki saari photos)
import argparse
import csv
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

from aruco_scale import rectify_with_marker
from inspect_crack import PPM, find_crack_mask, measure

TRUE_MM = [0.3, 0.5, 1.0, 2.0]          # sheet par upar se neeche
METHODS = ["classical", "dl"]
EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def find_lines(mask):
    """Mask mein ~80 mm lambi leti hui lines dhoondho. Return: har line ka mask, upar se neeche."""
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask, connectivity=8)
    # leti hui tukde: kam se kam 10 mm chaude, 6 mm se kam unche
    parts = [i for i in range(1, n)
             if st[i, cv2.CC_STAT_WIDTH] >= 10 * PPM and st[i, cv2.CC_STAT_HEIGHT] <= 6 * PPM]

    # ek hi line toot kar kai tukdon mein ho sakti hai -> same height (4 mm ke andar) wale jodo
    groups = []
    for i in sorted(parts, key=lambda i: cen[i, 1]):
        if groups and cen[i, 1] - cen[groups[-1][-1], 1] < 4 * PPM:
            groups[-1].append(i)
        else:
            groups.append([i])

    lines = []
    for g in groups:
        x0 = min(st[i, cv2.CC_STAT_LEFT] for i in g)
        x1 = max(st[i, cv2.CC_STAT_LEFT] + st[i, cv2.CC_STAT_WIDTH] for i in g)
        if not 70 * PPM <= x1 - x0 <= 90 * PPM:   # test line 80 mm ki hai
            continue
        line = np.isin(lab, g).astype(np.uint8) * 255
        # seedhi line ka skeleton ek seedhi rekha hota hai; ruler ke ticks / text usse hatt jaate hain
        sy, sx = np.nonzero(skeletonize(line > 0))
        resid = sy - np.polyval(np.polyfit(sx, sy, 1), sx)
        if np.std(resid) < 0.1 * PPM:
            lines.append(line)
    return lines


def measure_photo(path, marker_mm):
    """Ek photo -> {method: [4 widths ya None]} , ya error reason"""
    img = cv2.imread(str(path))
    if img is None:
        return None, "photo_not_opened"
    warped, _ = rectify_with_marker(img, marker_mm=marker_mm, px_per_mm=PPM)
    if warped is None:
        return None, "marker_not_found"

    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    found = {m: find_lines(find_crack_mask(warped, m)) for m in METHODS}

    # jis method ko chaaron lines mili, uski height (y) se line number tay karo
    ref = next((ls for ls in found.values() if len(ls) == len(TRUE_MM)), None)
    if ref is None:
        return None, "; ".join(f"{m}: {len(ls)} lines mili" for m, ls in found.items()) + ", 4 chahiye"
    ref_y = np.array([np.nonzero(l)[0].mean() for l in ref])

    out, notes = {}, []
    for m, lines in found.items():
        widths = [None] * len(TRUE_MM)
        for l in lines:
            dy = np.abs(ref_y - np.nonzero(l)[0].mean())
            k = int(np.argmin(dy))
            if dy[k] < 5 * PPM:
                # same tarika jo inspect_crack.py mein hai: skeleton par median sub-pixel width
                widths[k] = float(np.median(measure(l, gray)[2]))
        out[m] = widths
        if len(lines) != len(TRUE_MM):
            notes.append(f"{m}: {len(lines)} of 4 lines mili")
    return out, "; ".join(notes) or "ok"


def err_pct(measured, true):
    return None if measured is None else (measured - true) / true * 100


def fmt(v, spec):
    return "-" if v is None else format(v, spec)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="photo ya photos ka folder")
    ap.add_argument("marker_mm", nargs="?", type=float, default=50.0)
    ap.add_argument("--csv", default="line_results.csv")
    a = ap.parse_args()

    p = Path(a.path)
    photos = sorted(f for f in p.iterdir() if f.suffix.lower() in EXTS) if p.is_dir() else [p]
    if not photos:
        print("Koi photo nahi mili:", p)
        return

    rows = []
    for photo in photos:
        print(f"\n=== {photo.name}  (marker {a.marker_mm} mm)")
        res, status = measure_photo(photo, a.marker_mm)
        if res is None:
            print("  ERROR:", status)
            rows.append({"photo": photo.name, "status": status})
            continue
        print(f"  {'Line':<6}{'Asli':>7}{'Classical':>11}{'Galti':>9}{'DL':>8}{'Galti':>9}")
        for k, true in enumerate(TRUE_MM):
            c, d = res["classical"][k], res["dl"][k]
            ec, ed = err_pct(c, true), err_pct(d, true)
            pc = "-" if ec is None else f"{ec:+.0f}%"
            pd = "-" if ed is None else f"{ed:+.0f}%"
            print(f"  {k + 1:<6}{true:>7.2f}{fmt(c, '.2f'):>11}{pc:>9}{fmt(d, '.2f'):>8}{pd:>9}")
            rows.append({"photo": photo.name, "line": k + 1, "true_mm": true,
                         "classical_mm": fmt(c, ".3f"), "classical_err_pct": fmt(ec, ".1f"),
                         "dl_mm": fmt(d, ".3f"), "dl_err_pct": fmt(ed, ".1f"), "status": status})
        if status != "ok":
            print("  NOTE:", status)

    cols = ["photo", "line", "true_mm", "classical_mm", "classical_err_pct",
            "dl_mm", "dl_err_pct", "status"]
    with open(a.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{a.csv} save ho gaya ({len(rows)} rows)")


if __name__ == "__main__":
    main()

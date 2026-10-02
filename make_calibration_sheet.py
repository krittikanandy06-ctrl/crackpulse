# make_calibration_sheet.py - A4 calibration sheet PDF banao (600 DPI, 100% scale pe print karna)
# Sheet par: 50 mm ArUco marker, 100 mm ruler, aur 4 known-width lines (0.3 / 0.5 / 1.0 / 2.0 mm)
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

DPI = 600
PX_PER_MM = DPI / 25.4                  # 600 DPI par 1 mm = 23.62 px
PAGE_W_MM, PAGE_H_MM = 210, 297         # A4
MARKER_ID = 0
MARKER_MM = 50.0
OUT = "calibration_sheet.pdf"


def px(mm):
    return int(round(mm * PX_PER_MM))


def font(size_mm, bold=False):
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, px(size_mm))
        except OSError:
            pass
    return ImageFont.load_default(size=px(size_mm))


page = Image.new("1", (px(PAGE_W_MM), px(PAGE_H_MM)), 1)   # 1-bit: sirf kaala/safed, edges ekdum sharp
d = ImageDraw.Draw(page)
cx = page.width // 2

# --- 1. upar warning ---
d.text((cx, px(14)), "Print at 100% / Actual size. Do NOT fit to page.",
       font=font(6, bold=True), fill=0, anchor="mm")
d.text((cx, px(22)), "CrackPulse calibration sheet  |  A4  |  600 DPI",
       font=font(3.5), fill=0, anchor="mm")

# --- 2. ArUco marker (kaala hissa exactly 50 mm) ---
# 4x4 marker + 1 cell kaala border = 6x6 cells; nearest resize se edges sharp rehte hain
cells = cv2.aruco.generateImageMarker(
    cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), MARKER_ID, 6, borderBits=1)
side = px(MARKER_MM)
marker = cv2.resize(cells, (side, side), interpolation=cv2.INTER_NEAREST)
mx, my = cx - side // 2, px(45)
page.paste(Image.fromarray(marker).convert("1"), (mx, my))

# marker ke chaaron taraf 15 mm safed border; dashed line = yahan se kaato
q = px(15)
x0, y0, x1, y1 = mx - q, my - q, mx + side + q, my + side + q
dash, gap, lw = px(3), px(2), px(0.2)
for a in range(x0, x1, dash + gap):
    for y in (y0, y1):
        d.rectangle([a, y, min(a + dash, x1), y + lw], fill=0)
for a in range(y0, y1, dash + gap):
    for x in (x0, x1):
        d.rectangle([x, a, x + lw, min(a + dash, y1)], fill=0)
d.text((cx, y1 + px(5)), f"ArUco DICT_4X4_50, id {MARKER_ID}  |  black square = {MARKER_MM:.0f} mm  |  cut along dashed line",
       font=font(3), fill=0, anchor="mm")

# --- 3. 100 mm ruler ---
rx, ry = cx - px(50), px(150)                  # ruler ki baseline
tick_w = px(0.15)
d.rectangle([rx, ry, rx + px(100) + tick_w, ry + tick_w], fill=0)
for mm in range(101):
    x = rx + px(mm)
    h = 6 if mm % 10 == 0 else (4 if mm % 5 == 0 else 2.5)
    d.rectangle([x, ry - px(h), x + tick_w, ry], fill=0)
    if mm % 10 == 0:
        d.text((x, ry - px(h + 2.5)), str(mm), font=font(3), fill=0, anchor="mm")
d.text((cx, ry + px(6)), "100 mm ruler: 0 se 100 tak real ruler se naapo. Exactly 100 mm hona chahiye.",
       font=font(3), fill=0, anchor="mm")

# --- 4. chaar known-width lines (crack width test) ---
d.text((cx, px(178)), "Test lines (80 mm long)", font=font(4, bold=True), fill=0, anchor="mm")
lx = cx - px(50)
for i, w_mm in enumerate([0.3, 0.5, 1.0, 2.0]):
    yc = px(195 + i * 18)
    h = px(w_mm)                                # line ki motai pixel mein
    top = yc - h // 2
    d.rectangle([lx, top, lx + px(80) - 1, top + h - 1], fill=0)
    d.text((lx + px(86), yc), f"{w_mm} mm", font=font(4), fill=0, anchor="lm")

# --- 5. neeche instructions ---
notes = ["Print ke baad check karo:",
         "1. Marker ka kaala square ruler se naapo -> 50 mm hona chahiye.",
         "   Agar alag aaye (jaise 49.5 mm), to website/script mein marker_mm = 49.5 daalo.",
         "2. Ruler 100 mm hona chahiye. Galat ho to printer 'Fit to page' par tha, dobara print karo."]
for i, t in enumerate(notes):
    d.text((px(25), px(262) + i * px(6)), t, font=font(3), fill=0)

page.save(OUT, resolution=DPI)
print(f"{OUT} ban gaya: {page.width}x{page.height} px @ {DPI} DPI "
      f"= {page.width / DPI * 25.4:.1f} x {page.height / DPI * 25.4:.1f} mm")
print(f"Marker side: {side} px = {side / PX_PER_MM:.3f} mm")
for w_mm in [0.3, 0.5, 1.0, 2.0]:
    print(f"Line {w_mm} mm -> {px(w_mm)} px = {px(w_mm) / PX_PER_MM:.3f} mm")

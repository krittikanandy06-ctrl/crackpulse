# make_fake_sheet_photos.py - calibration_sheet.pdf se nakli "phone photos" banao (test_photos/ mein)
# Sheet ko ghumata, tircha karta, shadow/blur/noise daalta aur chhota karta hai.
import re
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def load_sheet(pdf="calibration_sheet.pdf"):
    """PDF ke andar ek hi 1-bit CCITT image hai; usko TIFF bana kar Pillow se kholo."""
    b = open(pdf, "rb").read()
    w = int(re.search(rb"/Width (\d+)", b)[1])
    h = int(re.search(rb"/Height (\d+)", b)[1])
    n = int(re.search(rb"/Length (\d+)", b)[1])
    start = re.search(rb"stream\r?\n", b).end()
    data = b[start:start + n]

    # chhota sa TIFF header: CCITT Group 4, PhotometricInterpretation 1 (0 = kaala)
    tags = [(256, 4, w), (257, 4, h), (258, 3, 1), (259, 3, 4), (262, 3, 1),
            (273, 4, 0), (278, 4, h), (279, 4, n)]
    ifd_size = 2 + 12 * len(tags) + 4
    offset = 8 + ifd_size
    t = b"II*\x00" + (8).to_bytes(4, "little") + len(tags).to_bytes(2, "little")
    for tag, typ, val in tags:
        val = offset if tag == 273 else val
        t += tag.to_bytes(2, "little") + typ.to_bytes(2, "little") + (1).to_bytes(4, "little")
        t += val.to_bytes(2, "little") + b"\x00\x00" if typ == 3 else val.to_bytes(4, "little")
    t += b"\x00\x00\x00\x00" + data
    return np.array(Image.open(BytesIO(t)).convert("L"))


def fake_photo(page, out_w, rot_deg, tilt, blur, noise, seed):
    rng = np.random.default_rng(seed)
    out_h = out_w * 4 // 3                       # phone jaisa 3:4 portrait
    hs = 0.82 * out_h                            # sheet frame ka 82% ucha
    ws = hs * 210 / 297

    # pehle INTER_AREA se lagbhag final size tak chhota karo (aliasing nahi hoga)
    s = hs / page.shape[0]
    small = cv2.resize(page, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape

    # tircha: upar wala kinara chhota (camera neeche se jhuka hua), phir ghumao
    cx, cy = out_w / 2, out_h / 2
    k = tilt * ws / 2
    dst = np.float32([[-ws / 2 + k, -hs / 2], [ws / 2 - k, -hs / 2],
                      [ws / 2, hs / 2], [-ws / 2, hs / 2]])
    dst += rng.normal(0, 0.01 * ws, dst.shape).astype(np.float32)
    r = np.deg2rad(rot_deg)
    R = np.float32([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])
    dst = dst @ R.T + np.float32([cx, cy])
    src = np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]])
    H = cv2.getPerspectiveTransform(src, dst)

    sheet = cv2.warpPerspective(small, H, (out_w, out_h), flags=cv2.INTER_LINEAR)
    inside = cv2.warpPerspective(np.full_like(small, 255), H, (out_w, out_h)) > 127

    # table (bhoora, thoda texture) + sheet
    table = cv2.GaussianBlur(rng.normal(95, 25, (out_h, out_w)).astype(np.float32), (0, 0), 6)
    img = np.where(inside, sheet.astype(np.float32), table)

    # roshni: ek kone se doosre tak 30% kam (shadow)
    yy, xx = np.mgrid[0:out_h, 0:out_w].astype(np.float32)
    img *= 1.0 - 0.3 * (xx / out_w + yy / out_h) / 2
    img = cv2.GaussianBlur(img, (0, 0), blur)
    img += rng.normal(0, noise, img.shape)

    # halka peela tint (ghar ki light), BGR
    bgr = np.stack([img * 0.92, img * 0.98, img * 1.0], axis=-1)
    return np.clip(bgr, 0, 255).astype(np.uint8)


if __name__ == "__main__":
    page = load_sheet()
    Path("test_photos").mkdir(exist_ok=True)
    variants = {                                 # out_w, ghumav (deg), tircha, blur, noise
        "sheet_mild.jpg":   (3024, 4, 0.05, 1.0, 3),
        "sheet_tilted.jpg": (3024, -12, 0.18, 1.5, 5),
        "sheet_lowres.jpg": (1500, 7, 0.10, 1.2, 4),
    }
    for i, (name, (w, rot, tilt, blur, noise)) in enumerate(variants.items()):
        img = fake_photo(page, w, rot, tilt, blur, noise, seed=i)
        cv2.imwrite(f"test_photos/{name}", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        ppm = 0.82 * w * 4 / 3 / 297
        print(f"test_photos/{name}: {img.shape[1]}x{img.shape[0]}, lagbhag {ppm:.1f} px/mm "
              f"(0.3 mm line = {0.3 * ppm:.1f} px)")

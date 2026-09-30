import cv2
import numpy as np
from skimage.morphology import skeletonize

FILE = "test_crack_card.png"
CARD_MM = 85.6   # card ki lambi side (mm)

img = cv2.imread(FILE)
if img is None:
    print("Photo nahi mili:", FILE)
    raise SystemExit

# photo ko chhota karo taaki screen par aaye (scale yaad rakho)
s = min(1.0, 900 / max(img.shape[:2]))
small = cv2.resize(img, None, fx=s, fy=s) if s < 1 else img.copy()

# --- 1. card ki LAMBI side ke dono kinaare click karo ---
points = []
work = small.copy()
win = "Card ki LAMBI side ke DONO kinaare click karo"


def click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 2:
        points.append((x, y))
        cv2.circle(work, (x, y), 5, (0, 0, 255), -1)


cv2.namedWindow(win)
cv2.setMouseCallback(win, click)
while len(points) < 2:
    cv2.imshow(win, work)
    if cv2.waitKey(20) == 27:
        raise SystemExit
cv2.destroyAllWindows()

(x1, y1), (x2, y2) = points
# click chhoti photo par hue, isliye asli photo ke hisaab se wapas badlo
card_px = float(np.hypot(x2 - x1, y2 - y1)) / s
px_per_mm = card_px / CARD_MM
print("1 mm =", round(px_per_mm, 2), "pixels")

# --- 2. sirf crack wala hissa chuno ---
x, y, w, h = cv2.selectROI(
    "Sirf crack wala hissa chuno, phir ENTER dabao", small)
cv2.destroyAllWindows()
if w == 0 or h == 0:
    print("Kuch chuna nahi.")
    raise SystemExit
x, y, w, h = [int(v / s) for v in (x, y, w, h)]
crop = img[y:y+h, x:x+w]

# --- 3. crack alag karo ---
gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (3, 3), 0)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
blackhat = cv2.morphologyEx(blur, cv2.MORPH_BLACKHAT, kernel)
_, mask = cv2.threshold(blackhat, 110, 255, cv2.THRESH_BINARY)

n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
clean = np.zeros_like(mask)
for i in range(1, n):
    if stats[i, cv2.CC_STAT_AREA] >= 60:
        clean[labels == i] = 255

# --- 4. width naapo ---
skel = skeletonize(clean > 0)
dist = cv2.distanceTransform(clean, cv2.DIST_L2, 5)
widths_mm = (dist[skel] * 2) / px_per_mm

print("Width (mm):")
print("  median :", round(float(np.median(widths_mm)), 2))
print("  90% points isse kam:", round(float(np.percentile(widths_mm, 90)), 2))

out = crop.copy()
out[clean == 255] = (0, 0, 255)
out[skel] = (0, 255, 0)
cv2.imwrite("step8_result.png", out)
print("step8_result.png dekho.")

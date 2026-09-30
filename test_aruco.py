# test_aruco.py - nakli tedhi photo banao (known crack width) aur check karo
import cv2
import numpy as np
from aruco_scale import rectify_with_marker

PPM_TRUE = 8.0                      # asli "deewar" par 1 mm = 8 px
W, H = int(300 * PPM_TRUE), int(200 * PPM_TRUE)
wall = np.full((H, W, 3), 190, np.uint8)
wall = cv2.add(wall, np.random.randint(0, 25, wall.shape, dtype=np.uint8))

# 50 mm marker
d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
m = cv2.aruco.generateImageMarker(d, 0, int(50 * PPM_TRUE))
pad = int(8 * PPM_TRUE)
x0, y0 = int(20 * PPM_TRUE), int(20 * PPM_TRUE)
wall[y0 - pad:y0 + m.shape[0] + pad, x0 - pad:x0 + m.shape[1] + pad] = 255
wall[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)

# crack: 1.5 mm chaudi tedhi-medhi line
pts = np.array([[int(110 * PPM_TRUE) + int(15 * PPM_TRUE * np.sin(t / 25.0)), t]
                for t in range(int(10 * PPM_TRUE), int(190 * PPM_TRUE))], np.int32)
cv2.polylines(wall, [pts], False, (40, 40, 40), int(round(1.5 * PPM_TRUE)))

# camera tedha rakha tha: perspective distortion
src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
dst = np.float32([[60, 40], [W - 20, 0], [W - 90, H - 10], [0, H - 60]])
photo = cv2.warpPerspective(wall, cv2.getPerspectiveTransform(src, dst), (W, H),
                            borderValue=(190, 190, 190))
cv2.imwrite("test_tilted.png", photo)

warped, ppm = rectify_with_marker(photo, marker_mm=50, px_per_mm=10)
cv2.imwrite("test_rectified.png", warped)

# width naapo (same idea jo tumhare code mein hai)
gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
_, mask = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY_INV)
n, lab, st, _ = cv2.connectedComponentsWithStats(mask)
big = 1 + np.argmax(st[1:, cv2.CC_STAT_HEIGHT])      # sabse lamba component = crack
crack = (lab == big).astype(np.uint8)
from skimage.morphology import skeletonize
skel = skeletonize(crack > 0)
dist = cv2.distanceTransform(crack, cv2.DIST_L2, 5)
w = dist[skel] * 2 / ppm
print(f"Asli width: 1.50 mm | Naapi gayi median: {np.median(w):.2f} mm")

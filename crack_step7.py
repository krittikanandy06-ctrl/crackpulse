import cv2
import numpy as np
from skimage.morphology import skeletonize

img = cv2.imread("crack.jpg")
mask = cv2.imread("mask.png", 0)

# crack ki beech wali patli line (skeleton)
skel = skeletonize(mask > 0)

# har point par crack kitni door tak faili hai
dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)

# skeleton par width = 2 x distance (pixels mein)
widths_px = dist[skel] * 2

print("Crack width (pixels mein):")
print("  average:", round(float(np.mean(widths_px)), 1))
print("  sabse zyada:", round(float(np.max(widths_px)), 1))

# mm mein badalne ke liye (abhi andaza hai, baad mein sahi karenge)
PIXELS_PER_MM = 5.0
print("Crack width (mm mein, andaza):")
print("  average:", round(float(np.mean(widths_px)) / PIXELS_PER_MM, 2))
print("  sabse zyada:", round(float(np.max(widths_px)) / PIXELS_PER_MM, 2))

# skeleton ko hare rang se dikhao
out = img.copy()
out[skel] = (0, 255, 0)
cv2.imwrite("skeleton.png", out)
print("skeleton.png dekho.")

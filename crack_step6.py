import cv2
import numpy as np

img = cv2.imread("crack.jpg")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)

# patli kaali lines ko ubharo (blackhat)
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
blackhat = cv2.morphologyEx(blur, cv2.MORPH_BLACKHAT, kernel)

# sirf pakki kaali lines rakho
_, mask = cv2.threshold(blackhat, 30, 255, cv2.THRESH_BINARY)

# chhote dhabbe (noise) hata do
n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
clean = np.zeros_like(mask)
for i in range(1, n):
    if stats[i, cv2.CC_STAT_AREA] >= 150:
        clean[labels == i] = 255

cv2.imwrite("mask.png", clean)

# original photo par crack ko laal rang do
overlay = img.copy()
overlay[clean == 255] = (0, 0, 255)
cv2.imwrite("overlay.png", overlay)
print("Ho gaya! mask.png aur overlay.png dekho.")

# make_marker.py - ArUco marker banao aur A4 par print karo
import cv2
import numpy as np

MARKER_ID = 0
MARKER_MM = 50          # print hone ke baad marker ki side 50 mm honi chahiye
DPI = 300               # printing resolution

side_px = int(round(MARKER_MM / 25.4 * DPI))        # 50 mm = 591 px @300 DPI
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
marker = cv2.aruco.generateImageMarker(dictionary, MARKER_ID, side_px)

# A4 page (210 x 297 mm), marker ke charon taraf safed jagah zaroori hai
a4 = np.full((int(297 / 25.4 * DPI), int(210 / 25.4 * DPI)), 255, np.uint8)
y0 = (a4.shape[0] - side_px) // 2
x0 = (a4.shape[1] - side_px) // 2
a4[y0:y0 + side_px, x0:x0 + side_px] = marker
cv2.putText(a4, f"ArUco 4x4 id={MARKER_ID}  side = {MARKER_MM} mm (print at 100%)",
            (80, y0 + side_px + 120), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 3)

cv2.imwrite("marker_A4.png", a4, [cv2.IMWRITE_PNG_COMPRESSION, 3])
print("marker_A4.png ban gaya. Print karte waqt 'Actual size / 100%' chuno.")
print("Print ke baad scale se black square naapo aur MARKER_MM usi number par set karo.")

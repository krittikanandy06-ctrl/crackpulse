# aruco_scale.py - photo mein ArUco marker dhoondho, perspective seedha karo, px_per_mm do
import cv2
import numpy as np

_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
_DETECTOR = cv2.aruco.ArucoDetector(_DICT, cv2.aruco.DetectorParameters())


def rectify_with_marker(img, marker_mm=50.0, px_per_mm=10.0, marker_id=0):
    """Photo ko aise warp karta hai jaise camera deewar ke bilkul saamne ho.
    Output image mein har jagah 1 mm = px_per_mm pixels.
    Return: (warped_img, px_per_mm)  ya marker na mile to (None, None)"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _DETECTOR.detectMarkers(gray)
    if ids is None or marker_id not in ids.flatten():
        return None, None

    idx = list(ids.flatten()).index(marker_id)
    src = corners[idx].reshape(4, 2).astype(np.float32)   # TL, TR, BR, BL

    # marker ko ek perfect square banana hai jiski side = marker_mm * px_per_mm
    s = marker_mm * px_per_mm
    dst_marker = np.float32([[0, 0], [s, 0], [s, s], [0, s]])
    H = cv2.getPerspectiveTransform(src, dst_marker)

    # poori photo ke kone warp karke dekho output kitna bada hoga
    h, w = img.shape[:2]
    box = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    box_w = cv2.perspectiveTransform(box, H).reshape(-1, 2)
    xmin, ymin = box_w.min(axis=0)
    xmax, ymax = box_w.max(axis=0)
    out_w, out_h = int(xmax - xmin), int(ymax - ymin)
    if out_w * out_h > 60_000_000:            # bahut tedhi photo = bekaar warp
        return None, None

    T = np.array([[1, 0, -xmin], [0, 1, -ymin], [0, 0, 1]], dtype=np.float64)
    warped = cv2.warpPerspective(img, T @ H, (out_w, out_h),
                                 flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    return warped, px_per_mm


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "crack.jpg"
    img = cv2.imread(path)
    warped, ppm = rectify_with_marker(img)
    if warped is None:
        print("Marker nahi mila. Photo mein poora marker saaf dikhna chahiye.")
    else:
        cv2.imwrite("rectified.png", warped)
        print(f"Marker mil gaya. rectified.png mein 1 mm = {ppm} pixels")

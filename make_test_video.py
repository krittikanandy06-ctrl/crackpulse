import cv2
import numpy as np

# ---- Asli jawab (ground truth) ----
FPS = 30
SECONDS = 10
FREQ_HZ = 3.0      # marker 3 baar per second hilega
AMP_MM = 2.0       # 2 mm upar-neeche
MARKER_MM = 50.0   # marker ka size
MARKER_PX = 200    # video mein marker kitne pixel ka

mm_per_px = MARKER_MM / MARKER_PX
amp_px = AMP_MM / mm_per_px

W, H = 960, 720
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
marker = cv2.aruco.generateImageMarker(dictionary, 0, MARKER_PX)

# Grey background, beech mein safed card pe marker
base = np.full((H, W), 170, np.uint8)
border = 40
card = np.full((MARKER_PX + 2 * border, MARKER_PX + 2 * border), 255, np.uint8)
card[border:border + MARKER_PX, border:border + MARKER_PX] = marker
y0 = (H - card.shape[0]) // 2
x0 = (W - card.shape[1]) // 2
base[y0:y0 + card.shape[0], x0:x0 + card.shape[1]] = card

out = cv2.VideoWriter("test_vibration.mp4",
                      cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
if not out.isOpened():
    print("ERROR: video file nahi ban payi")
    raise SystemExit

rng = np.random.default_rng(0)
for i in range(FPS * SECONDS):
    t = i / FPS
    dy = amp_px * np.sin(2 * np.pi * FREQ_HZ * t)
    M = np.float32([[1, 0, 0], [0, 1, dy]])
    frame = cv2.warpAffine(base, M, (W, H), borderValue=170)
    noise = rng.normal(0, 3, frame.shape)   # thoda camera noise
    frame = np.clip(frame + noise, 0, 255).astype(np.uint8)
    out.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))

out.release()
print("test_vibration.mp4 ban gaya")
print(f"Asli jawab -> {FREQ_HZ} Hz, {AMP_MM} mm, marker {MARKER_MM} mm")

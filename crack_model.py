# crack_model.py - trained U-Net (ONNX) ko OpenCV 5 DNN mein CPU par chalao
# Badi photo ko 384x384 ke tiles mein kaat kar chalata hai, phir jod deta hai.
import cv2
import numpy as np


class CrackSegmenter:
    def __init__(self, onnx_path="crack_unet.onnx", tile=384, overlap=64):
        self.net = cv2.dnn.readNetFromONNX(onnx_path)
        self.tile, self.overlap = tile, overlap

    def _infer(self, tile_bgr):
        # model ke andar normalization hai, isliye yahan sirf /255 aur BGR->RGB
        blob = cv2.dnn.blobFromImage(tile_bgr, 1 / 255.0, (self.tile, self.tile), swapRB=True)
        self.net.setInput(blob)
        return self.net.forward()[0, 0]

    def predict(self, img_bgr, scale=1.0):
        """Return: crack probability map (0..1), photo ke size ka"""
        src = img_bgr if scale == 1.0 else cv2.resize(img_bgr, None, fx=scale, fy=scale,
                                                      interpolation=cv2.INTER_AREA)
        h, w = src.shape[:2]
        t, step = self.tile, self.tile - self.overlap
        H = max(t, ((h - t + step - 1) // step) * step + t)
        W = max(t, ((w - t + step - 1) // step) * step + t)
        padded = cv2.copyMakeBorder(src, 0, H - h, 0, W - w, cv2.BORDER_REFLECT)

        # tile ke kinaare kam bharosemand hote hain -> beech ko zyada weight
        ramp = np.minimum(np.arange(t) + 1, t - np.arange(t)).astype(np.float32)
        weight = np.minimum.outer(ramp, ramp)
        acc = np.zeros((H, W), np.float32)
        wsum = np.zeros((H, W), np.float32)
        for y in range(0, H - t + 1, step):
            for x in range(0, W - t + 1, step):
                acc[y:y + t, x:x + t] += self._infer(padded[y:y + t, x:x + t]) * weight
                wsum[y:y + t, x:x + t] += weight
        prob = (acc / np.maximum(wsum, 1e-6))[:h, :w]
        if scale != 1.0:
            prob = cv2.resize(prob, (img_bgr.shape[1], img_bgr.shape[0]), interpolation=cv2.INTER_LINEAR)
        return prob


if __name__ == "__main__":
    import sys, time
    img = cv2.imread(sys.argv[1] if len(sys.argv) > 1 else "crack.jpg")
    seg = CrackSegmenter()
    t0 = time.time()
    prob = seg.predict(img)
    print(f"Time: {time.time() - t0:.2f} s | image {img.shape[1]}x{img.shape[0]}")
    cv2.imwrite("model_prob.png", (prob * 255).astype(np.uint8))
    print("model_prob.png dekho: safed = crack")

import cv2

# 1. photo kholo
img = cv2.imread("crack.jpg")
if img is None:
    print("crack.jpg nahi mili! Naam aur folder check karo.")
    raise SystemExit

# 2. photo ko kaala-safed karo
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 3. thoda blur karo (chhota noise hatane ke liye)
blur = cv2.GaussianBlur(gray, (5, 5), 0)

# 4. edges (kinare) dhundo, crack yahin dikhegi
edges = cv2.Canny(blur, 50, 150)

# 5. result save karo
cv2.imwrite("result.png", edges)
print("Ho gaya! result.png dekho.")
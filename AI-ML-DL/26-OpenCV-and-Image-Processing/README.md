# OpenCV & Image Processing — From Basics to Real-Time Applications

> Every concept has runnable Python code. Install: `pip install opencv-python numpy matplotlib`

---

## 1. OpenCV Basics

```python
import cv2
import numpy as np

# Reading/Writing images
img = cv2.imread('image.jpg')              # BGR format (not RGB!)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
cv2.imwrite('output.jpg', img)

# Image properties
height, width, channels = img.shape        # (H, W, C)
# OpenCV uses (H, W, C) — NumPy order
# NOT (C, H, W) like PyTorch!
print(f"Image: {width}x{height}, {channels} channels, dtype={img.dtype}")

# Pixel access
pixel = img[100, 200]                      # (B, G, R) at row=100, col=200
img[100, 200] = [255, 0, 0]               # Set pixel to blue

# Display (for scripts, not notebooks)
cv2.imshow('window', img)
cv2.waitKey(0)                             # 0 = wait forever
cv2.destroyAllWindows()

# For Jupyter notebooks, use matplotlib:
import matplotlib.pyplot as plt
plt.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))  # Convert BGR→RGB!
plt.axis('off')
plt.show()

# Create blank images
black = np.zeros((480, 640, 3), dtype=np.uint8)
white = np.ones((480, 640, 3), dtype=np.uint8) * 255
```

**Common pitfall:** OpenCV uses BGR, matplotlib uses RGB — always convert!

**Another pitfall:** `cv2.imread()` returns `None` silently if file not found — always check:
```python
img = cv2.imread('image.jpg')
if img is None:
    raise FileNotFoundError("Image not found!")
```

---

## 2. Image Operations

### Resizing

```python
# Resize to specific dimensions
resized = cv2.resize(img, (300, 200))  # (width, height) — NOT (H, W)!

# Resize by scale factor
half = cv2.resize(img, None, fx=0.5, fy=0.5)
double = cv2.resize(img, None, fx=2.0, fy=2.0)

# Interpolation methods:
# cv2.INTER_NEAREST  — fastest, blocky (use for masks/labels)
# cv2.INTER_LINEAR   — default, good for slight upscale
# cv2.INTER_AREA     — best for downscaling (anti-aliased)
# cv2.INTER_CUBIC    — better quality upscale, slower
# cv2.INTER_LANCZOS4 — highest quality upscale, slowest

# Rule: INTER_AREA for shrinking, INTER_CUBIC/LANCZOS4 for enlarging
small = cv2.resize(img, (100, 100), interpolation=cv2.INTER_AREA)
large = cv2.resize(img, (1000, 1000), interpolation=cv2.INTER_CUBIC)
```

### Cropping

```python
# Cropping is just NumPy slicing: img[y1:y2, x1:x2]
roi = img[50:200, 100:400]  # rows 50-200, cols 100-400

# Center crop
h, w = img.shape[:2]
crop_size = 224
start_x = (w - crop_size) // 2
start_y = (h - crop_size) // 2
center_crop = img[start_y:start_y+crop_size, start_x:start_x+crop_size]
```

### Rotating

```python
h, w = img.shape[:2]
center = (w // 2, h // 2)

# Get rotation matrix (center, angle, scale)
M = cv2.getRotationMatrix2D(center, 45, 1.0)  # 45° counter-clockwise
rotated = cv2.warpAffine(img, M, (w, h))

# Rotate without cropping (expand canvas)
M = cv2.getRotationMatrix2D(center, 45, 1.0)
cos = np.abs(M[0, 0])
sin = np.abs(M[0, 1])
new_w = int(h * sin + w * cos)
new_h = int(h * cos + w * sin)
M[0, 2] += (new_w - w) / 2
M[1, 2] += (new_h - h) / 2
rotated_full = cv2.warpAffine(img, M, (new_w, new_h))

# Simple 90° rotations (faster, no interpolation)
rot90 = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
rot180 = cv2.rotate(img, cv2.ROTATE_180)
rot270 = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
```

### Flipping

```python
horizontal = cv2.flip(img, 1)   # 1 = horizontal (mirror)
vertical = cv2.flip(img, 0)     # 0 = vertical (upside down)
both = cv2.flip(img, -1)        # -1 = both axes
```

### Color Space Conversions

```python
rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)     # For matplotlib/PIL
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)     # For color detection
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)   # For most processing
lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)     # Perceptual uniformity

# HSV ranges in OpenCV:
# H: 0-179 (NOT 0-360!)
# S: 0-255
# V: 0-255
```

### Drawing

```python
canvas = img.copy()  # Always draw on a copy!

# Rectangle: (image, top-left, bottom-right, color_BGR, thickness)
cv2.rectangle(canvas, (50, 50), (200, 200), (0, 255, 0), 2)
cv2.rectangle(canvas, (50, 50), (200, 200), (0, 255, 0), -1)  # filled

# Circle: (image, center, radius, color, thickness)
cv2.circle(canvas, (300, 300), 50, (0, 0, 255), 3)

# Line: (image, start, end, color, thickness)
cv2.line(canvas, (0, 0), (640, 480), (255, 0, 0), 2)

# Text: (image, text, origin, font, scale, color, thickness)
cv2.putText(canvas, 'Hello OpenCV', (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

# Polylines
pts = np.array([[100,50], [200,300], [50,200]], np.int32)
cv2.polylines(canvas, [pts], isClosed=True, color=(0,255,0), thickness=2)
```

### Blending (Transparency)

```python
# addWeighted: output = α*img1 + β*img2 + γ
blended = cv2.addWeighted(img1, 0.7, img2, 0.3, 0)
# 70% img1 + 30% img2 — great for overlays
```

---

## 3. Image Filtering & Processing

### Blurring / Smoothing

```python
# Gaussian Blur — general noise removal
# Kernel must be odd (3,5,7...). Larger = more blur.
blur = cv2.GaussianBlur(img, (5, 5), 0)  # 0 = auto sigma

# Median Blur — salt-and-pepper noise (preserves edges better)
median = cv2.medianBlur(img, 5)

# Bilateral Filter — smooth while preserving edges (slow but powerful)
# (src, diameter, sigmaColor, sigmaSpace)
bilateral = cv2.bilateralFilter(img, 9, 75, 75)

# Box (average) blur — simplest, rarely best choice
box = cv2.blur(img, (5, 5))
```

### Sharpening

```python
# Unsharp mask approach (best results)
blurred = cv2.GaussianBlur(img, (0, 0), 3)
sharpened = cv2.addWeighted(img, 1.5, blurred, -0.5, 0)

# Custom kernel approach
kernel = np.array([[-1, -1, -1],
                   [-1,  9, -1],
                   [-1, -1, -1]])
sharpened2 = cv2.filter2D(img, -1, kernel)
```

### Edge Detection

```python
# Sobel — directional gradients
sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)  # horizontal edges
sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)  # vertical edges
sobel_combined = cv2.magnitude(sobelx, sobely)

# Laplacian — second derivative (all directions)
laplacian = cv2.Laplacian(gray, cv2.CV_64F)

# Canny — best edge detector (multi-stage)
# low_threshold, high_threshold (try 1:2 or 1:3 ratio)
edges = cv2.Canny(gray, 50, 150)

# Tip: blur before Canny to reduce noise edges
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
edges_clean = cv2.Canny(blurred, 50, 150)
```

### Morphological Operations

```python
kernel = np.ones((5, 5), np.uint8)  # structuring element

# Erosion — shrinks white regions (removes small noise)
eroded = cv2.erode(binary, kernel, iterations=1)

# Dilation — grows white regions (fills small holes)
dilated = cv2.dilate(binary, kernel, iterations=1)

# Opening = erosion → dilation (remove small noise from foreground)
opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

# Closing = dilation → erosion (fill small holes in foreground)
closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

# Gradient = dilation - erosion (outline of objects)
gradient = cv2.morphologyEx(binary, cv2.MORPH_GRADIENT, kernel)

# Different kernel shapes
rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
ellipse_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
cross_kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (5, 5))
```

### Thresholding

```python
# Simple binary threshold
_, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
_, binary_inv = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

# Otsu's threshold — automatically finds optimal threshold
_, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

# Adaptive threshold — handles uneven lighting (USE THIS for documents!)
adaptive = cv2.adaptiveThreshold(gray, 255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,  # or ADAPTIVE_THRESH_MEAN_C
    cv2.THRESH_BINARY, 11, 2)        # blockSize=11, C=2

# When to use what:
# - Even lighting → Otsu
# - Uneven lighting → Adaptive
# - Known threshold → Simple binary
```

---

## 4. Contour Detection & Shape Analysis

```python
# Step 1: Convert to binary (threshold or Canny)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

# Step 2: Find contours
contours, hierarchy = cv2.findContours(
    binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
# RETR_EXTERNAL: only outer contours
# RETR_TREE: full hierarchy (nested contours)
# CHAIN_APPROX_SIMPLE: compress to endpoints (less memory)

# Step 3: Draw contours
output = img.copy()
cv2.drawContours(output, contours, -1, (0, 255, 0), 2)  # -1 = all

# Contour properties
for cnt in contours:
    area = cv2.contourArea(cnt)
    perimeter = cv2.arcLength(cnt, closed=True)
    
    # Bounding rectangle
    x, y, w, h = cv2.boundingRect(cnt)
    aspect_ratio = w / float(h)
    
    # Minimum enclosing circle
    (cx, cy), radius = cv2.minEnclosingCircle(cnt)
    
    # Centroid (center of mass)
    M = cv2.moments(cnt)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    
    # Contour approximation (simplify shape)
    epsilon = 0.02 * perimeter  # 2% of perimeter
    approx = cv2.approxPolyDP(cnt, epsilon, True)
    num_vertices = len(approx)
    # 3 vertices = triangle, 4 = rectangle, >8 ≈ circle
    
    # Convex hull
    hull = cv2.convexHull(cnt)
    
    # Solidity (area / convex hull area)
    hull_area = cv2.contourArea(hull)
    solidity = area / hull_area if hull_area > 0 else 0

# Filter contours by area (remove noise)
large_contours = [c for c in contours if cv2.contourArea(c) > 500]
```

### Practical: Count Objects in Image

```python
def count_objects(image_path, min_area=100):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, 
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Clean up with morphology
    kernel = np.ones((3, 3), np.uint8)
    clean = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
    
    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, 
                                    cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter small contours
    objects = [c for c in contours if cv2.contourArea(c) > min_area]
    
    # Draw results
    output = img.copy()
    for i, cnt in enumerate(objects):
        x, y, w, h = cv2.boundingRect(cnt)
        cv2.rectangle(output, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(output, str(i+1), (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    print(f"Found {len(objects)} objects")
    return output, len(objects)
```

---

## 5. Feature Detection & Matching

### Corner Detection

```python
# Harris Corner Detection
gray = np.float32(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
harris = cv2.cornerHarris(gray, blockSize=2, ksize=3, k=0.04)
# Mark corners on image
img[harris > 0.01 * harris.max()] = [0, 0, 255]

# Shi-Tomasi (Good Features to Track) — improved Harris
corners = cv2.goodFeaturesToTrack(gray, maxCorners=100,
                                   qualityLevel=0.01, minDistance=10)
for corner in corners:
    x, y = corner.ravel().astype(int)
    cv2.circle(img, (x, y), 5, (0, 255, 0), -1)
```

### Feature Descriptors

```python
# ORB — fast, free, good for real-time
orb = cv2.ORB_create(nfeatures=500)
keypoints, descriptors = orb.detectAndCompute(gray, None)

# SIFT — scale-invariant, more robust (free since OpenCV 4.4)
sift = cv2.SIFT_create()
keypoints, descriptors = sift.detectAndCompute(gray, None)

# AKAZE — good balance of speed and accuracy
akaze = cv2.AKAZE_create()
keypoints, descriptors = akaze.detectAndCompute(gray, None)

# Draw keypoints
img_kp = cv2.drawKeypoints(img, keypoints, None, 
                            flags=cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
```

### Feature Matching

```python
# Detect features in both images
orb = cv2.ORB_create(nfeatures=1000)
kp1, des1 = orb.detectAndCompute(gray1, None)
kp2, des2 = orb.detectAndCompute(gray2, None)

# Brute Force Matcher
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)  # HAMMING for ORB
matches = bf.knnMatch(des1, des2, k=2)

# Lowe's ratio test — filter bad matches
good_matches = []
for m, n in matches:
    if m.distance < 0.75 * n.distance:
        good_matches.append(m)

# Draw matches
match_img = cv2.drawMatches(img1, kp1, img2, kp2, good_matches, None,
                             flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

# FLANN matcher (faster for large feature sets, use with SIFT/SURF)
FLANN_INDEX_KDTREE = 1
index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
search_params = dict(checks=50)
flann = cv2.FlannBasedMatcher(index_params, search_params)
matches = flann.knnMatch(des1, des2, k=2)
```

### Homography Estimation

```python
# Find homography from matched points (requires ≥4 matches)
if len(good_matches) >= 4:
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1,1,2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1,1,2)
    
    # RANSAC removes outliers
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    
    # Warp image using homography
    h, w = img1.shape[:2]
    warped = cv2.warpPerspective(img1, H, (w, h))
```

---

## 6. Image Transformations

### Perspective Transform (Document Scanner)

```python
def order_points(pts):
    """Order points: top-left, top-right, bottom-right, bottom-left"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left has smallest sum
    rect[2] = pts[np.argmax(s)]   # bottom-right has largest sum
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]   # top-right has smallest difference
    rect[3] = pts[np.argmax(d)]   # bottom-left has largest difference
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    # Compute width and height of new image
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = int(max(widthA, widthB))
    
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = int(max(heightA, heightB))
    
    # Destination points
    dst = np.array([
        [0, 0], [maxWidth-1, 0],
        [maxWidth-1, maxHeight-1], [0, maxHeight-1]
    ], dtype="float32")
    
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxWidth, maxHeight))
```

### Histogram Equalization

```python
# Global histogram equalization (can over-enhance)
equalized = cv2.equalizeHist(gray)

# CLAHE — Contrast Limited Adaptive Histogram Equalization (BETTER)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
enhanced = clahe.apply(gray)

# CLAHE on color images (apply to L channel in LAB)
lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
l, a, b = cv2.split(lab)
l_enhanced = clahe.apply(l)
enhanced_color = cv2.merge([l_enhanced, a, b])
enhanced_color = cv2.cvtColor(enhanced_color, cv2.COLOR_LAB2BGR)
```

---

## 7. Video Processing

### Basic Video Read/Write

```python
import cv2
import time

# Read from webcam
cap = cv2.VideoCapture(0)

# Read from file
cap = cv2.VideoCapture('video.mp4')

# Check if opened
if not cap.isOpened():
    raise IOError("Cannot open video source")

# Get video properties
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# Write video output
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('output.mp4', fourcc, fps, (width, height))

# FPS calculation
prev_time = time.time()

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    # --- Process frame here ---
    processed = cv2.GaussianBlur(frame, (5, 5), 0)
    
    # FPS overlay
    curr_time = time.time()
    fps_display = 1 / (curr_time - prev_time)
    prev_time = curr_time
    cv2.putText(processed, f'FPS: {fps_display:.1f}', (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    out.write(processed)
    cv2.imshow('Video', processed)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
out.release()
cv2.destroyAllWindows()
```

### Background Subtraction

```python
cap = cv2.VideoCapture('traffic.mp4')
bg_subtractor = cv2.createBackgroundSubtractorMOG2(
    history=500, varThreshold=50, detectShadows=True)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    # Apply background subtraction
    fg_mask = bg_subtractor.apply(frame)
    
    # Clean mask
    kernel = np.ones((5, 5), np.uint8)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
    
    # Find moving objects
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        if cv2.contourArea(cnt) > 500:
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
    
    cv2.imshow('Frame', frame)
    cv2.imshow('FG Mask', fg_mask)
    if cv2.waitKey(30) & 0xFF == ord('q'):
        break
```

### Optical Flow (Motion Estimation)

```python
cap = cv2.VideoCapture('video.mp4')
ret, prev_frame = cap.read()
prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Dense optical flow (Farneback)
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    
    # Visualize flow as color
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv = np.zeros_like(frame)
    hsv[..., 0] = ang * 180 / np.pi / 2
    hsv[..., 1] = 255
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    flow_rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    
    cv2.imshow('Optical Flow', flow_rgb)
    prev_gray = gray
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
```

### Object Tracking

```python
# Available trackers (OpenCV 4.x)
TRACKERS = {
    'csrt': cv2.TrackerCSRT_create,      # Accurate, slower
    'kcf': cv2.TrackerKCF_create,        # Good balance
    'mosse': cv2.legacy.TrackerMOSSE_create,  # Fastest, less accurate
}

cap = cv2.VideoCapture('video.mp4')
ret, frame = cap.read()

# Select ROI to track
bbox = cv2.selectROI('Select Object', frame, fromCenter=False)
cv2.destroyWindow('Select Object')

# Initialize tracker
tracker = cv2.TrackerCSRT_create()
tracker.init(frame, bbox)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    success, bbox = tracker.update(frame)
    if success:
        x, y, w, h = [int(v) for v in bbox]
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
    else:
        cv2.putText(frame, "Lost", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    
    cv2.imshow('Tracking', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
```

### Threaded Video Capture (Performance)

```python
from threading import Thread
import cv2

class VideoStream:
    """Threaded video capture — separates I/O from processing."""
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
    
    def start(self):
        Thread(target=self._update, daemon=True).start()
        return self
    
    def _update(self):
        while not self.stopped:
            self.ret, self.frame = self.cap.read()
    
    def read(self):
        return self.frame
    
    def stop(self):
        self.stopped = True
        self.cap.release()

# Usage — typically 20-30% FPS improvement
vs = VideoStream(0).start()
while True:
    frame = vs.read()
    # process frame...
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
vs.stop()
```

---

## 8. Real-World Projects

### Project 1: Document Scanner (~30 lines)

```python
def scan_document(image_path):
    img = cv2.imread(image_path)
    orig = img.copy()
    
    # Preprocess
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 200)
    
    # Find largest contour (the paper)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, 
                                    cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:  # Found rectangle
            doc_contour = approx
            break
    
    # Perspective transform
    pts = doc_contour.reshape(4, 2).astype("float32")
    scanned = four_point_transform(orig, pts)  # from Section 6
    
    # Clean up (convert to B&W document)
    scanned_gray = cv2.cvtColor(scanned, cv2.COLOR_BGR2GRAY)
    scanned_bw = cv2.adaptiveThreshold(scanned_gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    return scanned_bw
```

### Project 2: Face Detection (~20 lines)

```python
# Method 1: Haar Cascades (fast, less accurate)
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

img = cv2.imread('people.jpg')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, 
                                       minNeighbors=5, minSize=(30, 30))
for (x, y, w, h) in faces:
    cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

# Method 2: DNN-based (more accurate, handles angles)
net = cv2.dnn.readNetFromCaffe(
    'deploy.prototxt', 'res10_300x300_ssd_iter_140000.caffemodel')

blob = cv2.dnn.blobFromImage(img, 1.0, (300, 300), (104, 177, 123))
net.setInput(blob)
detections = net.forward()

h, w = img.shape[:2]
for i in range(detections.shape[2]):
    confidence = detections[0, 0, i, 2]
    if confidence > 0.5:
        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
        (x1, y1, x2, y2) = box.astype("int")
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, f'{confidence:.2f}', (x1, y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
```

### Project 3: Color-Based Object Tracking (~25 lines)

```python
def track_color(color_lower, color_upper):
    """Track objects of a specific color in real-time."""
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Convert to HSV and create mask
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, color_lower, color_upper)
        
        # Clean mask
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5,5), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))
        
        # Find and track largest contour
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > 500:
                x, y, w, h = cv2.boundingRect(largest)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cx, cy = x + w//2, y + h//2
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
        
        cv2.imshow('Tracking', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()

# Track blue objects
track_color(np.array([100, 50, 50]), np.array([130, 255, 255]))
```

### Project 4: Motion Detection (~20 lines)

```python
def detect_motion(video_source=0, threshold=25, min_area=500):
    cap = cv2.VideoCapture(video_source)
    ret, prev_frame = cap.read()
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    prev_gray = cv2.GaussianBlur(prev_gray, (21, 21), 0)
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Frame difference
        diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        motion = False
        for cnt in contours:
            if cv2.contourArea(cnt) > min_area:
                motion = True
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        status = "MOTION DETECTED" if motion else "No motion"
        cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 0, 255) if motion else (0, 255, 0), 2)
        
        cv2.imshow('Motion', frame)
        prev_gray = gray
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
```

### Project 5: Lane Detection (~40 lines)

```python
def detect_lanes(image):
    h, w = image.shape[:2]
    
    # Convert to grayscale and detect edges
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    
    # Region of Interest (bottom half triangle)
    mask = np.zeros_like(edges)
    polygon = np.array([[
        (0, h), (w, h), (w//2, h//2)
    ]])
    cv2.fillPoly(mask, polygon, 255)
    masked_edges = cv2.bitwise_and(edges, mask)
    
    # Hough Line Transform
    lines = cv2.HoughLinesP(masked_edges, rho=1, theta=np.pi/180,
                             threshold=50, minLineLength=50, maxLineGap=150)
    
    # Separate left and right lanes by slope
    left_lines, right_lines = [], []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            slope = (y2 - y1) / (x2 - x1 + 1e-6)
            if slope < -0.5:
                left_lines.append(line[0])
            elif slope > 0.5:
                right_lines.append(line[0])
    
    # Draw lanes
    line_image = np.zeros_like(image)
    for lines_group, color in [(left_lines, (255, 0, 0)), 
                                (right_lines, (0, 0, 255))]:
        if lines_group:
            for x1, y1, x2, y2 in lines_group:
                cv2.line(line_image, (x1, y1), (x2, y2), color, 5)
    
    # Overlay on original
    result = cv2.addWeighted(image, 0.8, line_image, 1.0, 0)
    return result
```

---

## 9. OpenCV + Deep Learning

```python
# === Load models from different frameworks ===

# ONNX (recommended — universal format)
net = cv2.dnn.readNetFromONNX('model.onnx')

# Darknet (YOLO)
net = cv2.dnn.readNetFromDarknet('yolov3.cfg', 'yolov3.weights')

# TensorFlow
net = cv2.dnn.readNetFromTensorflow('frozen_graph.pb', 'graph.pbtxt')

# Caffe
net = cv2.dnn.readNetFromCaffe('deploy.prototxt', 'model.caffemodel')

# === Run inference ===
# blobFromImage: resize, normalize, swap channels
blob = cv2.dnn.blobFromImage(
    img,
    scalefactor=1/255.0,     # normalize to [0,1]
    size=(416, 416),         # model input size
    mean=(0, 0, 0),          # subtract mean
    swapRB=True,             # BGR → RGB
    crop=False
)

net.setInput(blob)
output_layers = net.getUnconnectedOutLayersNames()
outputs = net.forward(output_layers)

# === YOLO post-processing example ===
boxes, confidences, class_ids = [], [], []
h, w = img.shape[:2]

for output in outputs:
    for detection in output:
        scores = detection[5:]
        class_id = np.argmax(scores)
        confidence = scores[class_id]
        
        if confidence > 0.5:
            cx, cy, bw, bh = detection[0:4] * np.array([w, h, w, h])
            x = int(cx - bw / 2)
            y = int(cy - bh / 2)
            boxes.append([x, y, int(bw), int(bh)])
            confidences.append(float(confidence))
            class_ids.append(class_id)

# Non-Maximum Suppression (remove overlapping boxes)
indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
for i in indices.flatten():
    x, y, w, h = boxes[i]
    cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)
```

**When to use OpenCV DNN vs PyTorch/TensorFlow:**

| | OpenCV DNN | PyTorch / TensorFlow |
|---|---|---|
| Use for | Deployment, inference only | Training + inference |
| GPU required | No (CPU is decent) | Yes (for training) |
| Model size | Lightweight runtime | Heavy frameworks |
| Speed (CPU) | Optimized | Slower |
| Model support | Limited (popular ones) | Everything |
| Install size | ~50MB | ~1-2GB |

---

## 10. Performance Tips

```python
# 1. NEVER loop over pixels — use NumPy vectorization
# BAD (30 seconds for 1080p):
for y in range(h):
    for x in range(w):
        img[y, x] = img[y, x] * 1.5

# GOOD (instant):
img = np.clip(img * 1.5, 0, 255).astype(np.uint8)

# 2. Resize before heavy operations
small = cv2.resize(img, None, fx=0.5, fy=0.5)
# Process on small, scale results back up

# 3. Use ROI to limit processing area
roi = frame[100:400, 200:500]
# Process only ROI, not full frame

# 4. Choose right data types
gray = gray.astype(np.uint8)  # Not float64!

# 5. Reuse allocated arrays (avoid GC pressure)
output = np.empty_like(frame)
cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY, dst=output[:,:,0])

# 6. Use cv2.UMat for transparent OpenCL acceleration
umat = cv2.UMat(img)
blurred = cv2.GaussianBlur(umat, (5,5), 0)
result = blurred.get()  # back to numpy

# 7. Profile your pipeline
import time
t = time.time()
# ... operation ...
print(f"Operation took: {(time.time()-t)*1000:.1f}ms")
```

---

## 11. OpenCV vs Pillow vs scikit-image

| Task | OpenCV | Pillow | scikit-image |
|------|--------|--------|--------------|
| Real-time video | **Best** | No | No |
| Image loading | Fast (NumPy) | Simple (PIL.Image) | Slow |
| Filtering | **Fastest** | Basic | Good (via scipy) |
| Feature detection | **Best** | No | Good |
| DL inference | Yes (DNN module) | No | No |
| Augmentation | Good | Basic | Good |
| Color format | BGR (annoying) | RGB | RGB |
| API style | C++ bindings | Pythonic | Pythonic/scikit |
| Install size | ~50MB | ~5MB | ~30MB |

**Decision guide:**
- **OpenCV** — production computer vision, real-time, video, deployment
- **Pillow** — simple load/save/resize, web apps, thumbnails
- **scikit-image** — scientific analysis, research, clean API

---

## 12. Common Interview Questions

### Q1: Why does OpenCV use BGR instead of RGB?
Historical reason — when OpenCV was created (1999), BGR was the default format for camera manufacturers and Windows bitmap format. It stuck for backward compatibility.

### Q2: What's the difference between erosion and dilation?
- **Erosion**: Shrinks white (foreground) regions. A pixel stays white only if ALL pixels under the kernel are white. Removes small noise.
- **Dilation**: Grows white regions. A pixel becomes white if ANY pixel under the kernel is white. Fills small holes.

### Q3: When would you use adaptive thresholding over Otsu's?
Adaptive thresholding when lighting is **uneven** across the image (e.g., photographed document with shadows). Otsu's finds a single global threshold — fails with uneven illumination.

### Q4: Explain the Canny edge detector steps.
1. **Gaussian blur** — reduce noise
2. **Gradient calculation** — Sobel in x and y directions
3. **Non-maximum suppression** — thin edges to 1-pixel width
4. **Hysteresis thresholding** — two thresholds: strong edges (>high), weak edges (between low and high, kept only if connected to strong)

### Q5: How does Lowe's ratio test work for feature matching?
For each feature in image 1, find the 2 best matches in image 2. If the best match distance is significantly less than the second-best (ratio < 0.75), it's likely a true match. If both matches are similar in distance, the match is ambiguous and rejected.

### Q6: How would you detect a specific colored object in a video stream?
1. Convert frame to HSV (more robust to lighting than RGB)
2. Define color range (lower/upper HSV bounds)
3. Create binary mask with `cv2.inRange()`
4. Clean mask with morphological operations
5. Find contours in mask
6. Get bounding box of largest contour

---

## Quick Reference: Most-Used Functions

```python
# I/O
cv2.imread(path)                    # Read image
cv2.imwrite(path, img)              # Save image
cv2.VideoCapture(source)            # Open video/camera

# Conversion
cv2.cvtColor(img, code)             # Color space conversion
cv2.resize(img, (w, h))             # Resize

# Filtering
cv2.GaussianBlur(img, (k,k), 0)    # Blur
cv2.Canny(gray, low, high)          # Edge detection
cv2.threshold(gray, t, max, type)   # Thresholding

# Drawing
cv2.rectangle(img, pt1, pt2, color, thickness)
cv2.circle(img, center, r, color, thickness)
cv2.putText(img, text, org, font, scale, color, thickness)

# Contours
cv2.findContours(binary, mode, method)
cv2.drawContours(img, contours, idx, color, thickness)
cv2.contourArea(cnt)
cv2.boundingRect(cnt)

# Transforms
cv2.warpPerspective(img, M, (w, h))
cv2.warpAffine(img, M, (w, h))

# DNN
cv2.dnn.readNetFromONNX(path)
cv2.dnn.blobFromImage(img, scale, size, mean, swapRB)
```

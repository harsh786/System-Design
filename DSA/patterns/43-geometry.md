# 43 - Computational Geometry

## When Geometry Shows Up in Interviews

Rare but high-impact. Companies like Google, Meta, and robotics firms ask these. If you see coordinates, points, or spatial relationships — you're in geometry territory. The key differentiator: **can you avoid floating point entirely?**

---

## Decision Flowchart

```
Given points/coordinates?
├── Distance-based?
│   ├── K closest → Heap / Quickselect [Pattern 9]
│   ├── Closest pair → Divide & Conquer [Pattern 6]
│   └── Which metric? → Euclidean / Manhattan / Chebyshev [Pattern 1]
├── Orientation / Turn direction?
│   ├── Collinearity → Cross Product [Pattern 2]
│   ├── Max points on line → GCD slope [Pattern 7]
│   └── Convex Hull → Graham / Andrew's [Pattern 3]
├── Intersection?
│   ├── Line/segment intersection → Parametric [Pattern 4]
│   └── Point in polygon → Ray casting [Pattern 5]
├── Shape detection?
│   ├── Square/Rectangle → Distance + property check [Pattern 8]
│   └── Min area rectangle → HashSet + diagonal [Pattern 10]
└── Movement/path?
    └── Robot bounded → Simulate + direction [Pattern 12]
```

---

## Coordinate Geometry Cheat Sheet

| Formula | Expression | Integer-Safe? |
|---------|-----------|---------------|
| Euclidean² | `(x2-x1)² + (y2-y1)²` | Yes (compare squared) |
| Manhattan | `|x2-x1| + |y2-y1|` | Yes |
| Chebyshev | `max(|x2-x1|, |y2-y1|)` | Yes |
| Cross Product | `(b-a) × (c-a) = (bx-ax)(cy-ay) - (by-ay)(cx-ax)` | Yes |
| Dot Product | `(b-a) · (c-a) = (bx-ax)(cx-ax) + (by-ay)(cy-ay)` | Yes |
| Area of Triangle | `|cross product| / 2` | Half-integer |
| Slope (avoid) | `dy/dx` → use `(dy, dx)` normalized by GCD | Yes |
| Collinear | `cross product == 0` | Yes |
| On segment | collinear + within bounding box | Yes |

### Floating Point Pitfalls

```
NEVER: slope = (double)(y2-y1) / (x2-x1)   // precision loss, division by zero
NEVER: angle = Math.atan2(dy, dx)            // unnecessary, loses precision
NEVER: distance = Math.sqrt(dx*dx + dy*dy)   // compare squared distances instead

ALWAYS: use cross product for orientation (no division)
ALWAYS: represent slope as reduced (dy, dx) pair via GCD
ALWAYS: compare squared distances when only ordering matters
ALWAYS: use long for intermediate products to avoid int overflow
```

---

## Pattern 1: Distance Calculations

### Signal
- "K closest points", "nearest neighbor", distance constraint
- Grid movement with different movement rules

### When to Use Which

| Metric | Movement Model | Use Case |
|--------|---------------|----------|
| Euclidean | Free movement (drone, bird) | Closest points, circle queries |
| Manhattan | Grid, 4-directional (taxi, robot) | City block distance, BFS on grid |
| Chebyshev | Grid, 8-directional (king in chess) | Chessboard distance |

**Key insight**: Chebyshev(a,b) = Manhattan after 45° rotation: `(x,y) → (x+y, x-y)`

### Template

```java
// Compare distances without sqrt — avoids floating point
long euclideanSquared(int[] a, int[] b) {
    long dx = a[0] - b[0], dy = a[1] - b[1];
    return dx * dx + dy * dy;  // use long to avoid overflow
}

int manhattan(int[] a, int[] b) {
    return Math.abs(a[0] - b[0]) + Math.abs(a[1] - b[1]);
}

int chebyshev(int[] a, int[] b) {
    return Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]));
}

// Manhattan ↔ Chebyshev transform (45° rotation)
// Chebyshev in original = Manhattan in rotated
// Useful for: "min moves for king" or "max Manhattan distance" problems
int[] rotate45(int x, int y) {
    return new int[]{x + y, x - y};
}
```

### Visualization

```
Euclidean (circle):     Manhattan (diamond):    Chebyshev (square):
      . * .                   *                  * * * * *
    * * * * *               * * *                * * * * *
  * * * O * * *           * * O * *              * * O * *
    * * * * *               * * *                * * * * *
      . * .                   *                  * * * * *
  
  All points at           All points at          All points at
  distance ≤ 2            distance ≤ 2           distance ≤ 2
```

### Complexity
- Single distance: O(1)
- All pairs: O(n²)

---

## Pattern 2: Cross Product / Orientation Test

### Signal
- Need to determine turn direction (left/right)
- Collinearity check, area calculation
- Foundation for convex hull, polygon algorithms

### Template

```java
// Returns:
//   > 0 : counterclockwise (left turn)
//   = 0 : collinear
//   < 0 : clockwise (right turn)
long cross(int[] O, int[] A, int[] B) {
    return (long)(A[0] - O[0]) * (B[1] - O[1]) 
         - (long)(A[1] - O[1]) * (B[0] - O[0]);
}

// Three-point orientation
int orientation(int[] p, int[] q, int[] r) {
    long val = cross(p, q, r);
    if (val == 0) return 0;      // collinear
    return val > 0 ? 1 : -1;    // CCW : CW
}

// Check if point C lies on segment AB (given collinear)
boolean onSegment(int[] A, int[] B, int[] C) {
    return Math.min(A[0], B[0]) <= C[0] && C[0] <= Math.max(A[0], B[0])
        && Math.min(A[1], B[1]) <= C[1] && C[1] <= Math.max(A[1], B[1]);
}
```

### Visualization

```
Cross product of vectors OA and OB:

  B                    A
   \  CCW (+)         /  CW (-)
    \               /
     O—————A       O—————B

         A———B  Collinear (0)
        /
       O
```

### Complexity
- O(1) per orientation test

---

## Pattern 3: Convex Hull (Andrew's Monotone Chain)

### Signal
- "Outermost points", "fence", "rubber band around nails"
- Need boundary enclosing all points
- LC 587: Erect the Fence

### Template

```java
// Andrew's Monotone Chain — O(n log n)
// Returns convex hull in CCW order
public int[][] convexHull(int[][] points) {
    int n = points.length;
    if (n <= 3) return points;  // edge case handling needed
    
    // Sort by x, then by y
    Arrays.sort(points, (a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
    
    int[][] hull = new int[2 * n][];
    int k = 0;
    
    // Build lower hull
    for (int i = 0; i < n; i++) {
        // For strict convex hull: use < 0
        // To include collinear points on edge: use < 0 still but handle separately
        while (k >= 2 && cross(hull[k-2], hull[k-1], points[i]) < 0)
            k--;
        hull[k++] = points[i];
    }
    
    // Build upper hull
    int lower = k + 1;
    for (int i = n - 2; i >= 0; i--) {
        while (k >= lower && cross(hull[k-2], hull[k-1], points[i]) < 0)
            k--;
        hull[k++] = points[i];
    }
    
    return Arrays.copyOf(hull, k - 1);  // k-1: remove duplicate last point
}

long cross(int[] O, int[] A, int[] B) {
    return (long)(A[0] - O[0]) * (B[1] - O[1]) 
         - (long)(A[1] - O[1]) * (B[0] - O[0]);
}
```

### Visualization

```
Input points:           Convex Hull:
                        
  *   *   *               *———————*
    *       *           / *       * \
  *   *   *           *   *   *     *
      *               |     *       |
  *       *           *             *
                       \           /
                        *—————————*

Lower hull: left→right, keep right turns
Upper hull: right→left, keep right turns
```

### Variants
- **Include collinear boundary points** (LC 587): change `< 0` to `<= 0` BUT must handle collinear points on last edge separately (sort them by distance in reverse for upper hull's last segment)
- **Graham Scan**: pick lowest point, sort by polar angle, process in order. Same complexity but trickier with collinear points.

### Complexity
- Time: O(n log n) — dominated by sort
- Space: O(n)

---

## Pattern 4: Line Intersection

### Signal
- "Do segments intersect?", "intersection point"
- Sweep line prerequisites

### Template

```java
// Check if segments (p1,q1) and (p2,q2) intersect
boolean segmentsIntersect(int[] p1, int[] q1, int[] p2, int[] q2) {
    int o1 = sign(cross(p1, q1, p2));
    int o2 = sign(cross(p1, q1, q2));
    int o3 = sign(cross(p2, q2, p1));
    int o4 = sign(cross(p2, q2, q1));
    
    // General case: segments straddle each other
    if (o1 != o2 && o3 != o4) return true;
    
    // Collinear special cases
    if (o1 == 0 && onSegment(p1, q1, p2)) return true;
    if (o2 == 0 && onSegment(p1, q1, q2)) return true;
    if (o3 == 0 && onSegment(p2, q2, p1)) return true;
    if (o4 == 0 && onSegment(p2, q2, q1)) return true;
    
    return false;
}

int sign(long x) { return x > 0 ? 1 : x < 0 ? -1 : 0; }

// Parametric intersection point (when you need coordinates)
// Line 1: P + t*(Q-P), Line 2: R + u*(S-R)
// Returns t parameter; intersection at P + t*(Q-P)
// Returns null if parallel
Double intersectionParam(double[] P, double[] Q, double[] R, double[] S) {
    double d = (Q[0]-P[0])*(S[1]-R[1]) - (Q[1]-P[1])*(S[0]-R[0]);
    if (Math.abs(d) < 1e-10) return null;  // parallel
    double t = ((R[0]-P[0])*(S[1]-R[1]) - (R[1]-P[1])*(S[0]-R[0])) / d;
    return t;  // valid segment intersection if 0 <= t <= 1 and 0 <= u <= 1
}
```

### Visualization

```
Straddle test using orientation:

    q2
    |        o1 = orient(p1,q1,p2) = CW (-)
    |        o2 = orient(p1,q1,q2) = CCW (+)
p1——X——q1   o3 = orient(p2,q2,p1) = CCW (+)
    |        o4 = orient(p2,q2,q1) = CW (-)
    |
    p2       Different signs → intersect!
```

### Complexity
- O(1) per intersection test

---

## Pattern 5: Point in Polygon (Ray Casting)

### Signal
- "Is point inside polygon?"
- Geofencing, containment checks

### Template

```java
// Ray casting: cast horizontal ray to the right, count edge crossings
// Odd crossings = inside, Even = outside
boolean pointInPolygon(int[] point, int[][] polygon) {
    int n = polygon.length;
    boolean inside = false;
    int px = point[0], py = point[1];
    
    for (int i = 0, j = n - 1; i < n; j = i++) {
        int xi = polygon[i][0], yi = polygon[i][1];
        int xj = polygon[j][0], yj = polygon[j][1];
        
        // Check if ray crosses this edge
        if ((yi > py) != (yj > py) &&
            px < (long)(xj - xi) * (py - yi) / (yj - yi) + xi) {
            inside = !inside;
        }
    }
    return inside;
}
```

### Visualization

```
Ray casting from point P:

    ___________
   /           \        Ray →→→→→→→→→→→→
  /    P • ——————————X———————X——→  (2 crossings = outside? No!)
 /             \     Wait — P is inside, ray crosses 2 edges...
 \     • Q ——————X———————————————→  (1 crossing = inside ✓)
  \___________/

Odd crossings = INSIDE
Even crossings = OUTSIDE
```

### Complexity
- O(n) per query where n = polygon vertices

---

## Pattern 6: Closest Pair of Points

### Signal
- "Find two closest points" in large point set
- Need better than O(n²) brute force

### Template

```java
public double closestPair(int[][] points) {
    int[][] sortedX = points.clone();
    Arrays.sort(sortedX, (a, b) -> a[0] - b[0]);
    return closestRec(sortedX, 0, sortedX.length - 1);
}

double closestRec(int[][] pts, int lo, int hi) {
    if (hi - lo < 3) return bruteForce(pts, lo, hi);
    
    int mid = (lo + hi) / 2;
    int midX = pts[mid][0];
    
    double dl = closestRec(pts, lo, mid);
    double dr = closestRec(pts, mid + 1, hi);
    double d = Math.min(dl, dr);
    
    // Build strip of points within distance d of midline
    List<int[]> strip = new ArrayList<>();
    for (int i = lo; i <= hi; i++) {
        if (Math.abs(pts[i][0] - midX) < d)
            strip.add(pts[i]);
    }
    
    // Sort strip by y and check nearby points
    strip.sort((a, b) -> a[1] - b[1]);
    for (int i = 0; i < strip.size(); i++) {
        // Only need to check next 7 points (proven geometric bound)
        for (int j = i + 1; j < strip.size() && 
             (strip.get(j)[1] - strip.get(i)[1]) < d; j++) {
            d = Math.min(d, dist(strip.get(i), strip.get(j)));
        }
    }
    return d;
}

double dist(int[] a, int[] b) {
    double dx = a[0] - b[0], dy = a[1] - b[1];
    return Math.sqrt(dx * dx + dy * dy);
}

double bruteForce(int[][] pts, int lo, int hi) {
    double min = Double.MAX_VALUE;
    for (int i = lo; i <= hi; i++)
        for (int j = i + 1; j <= hi; j++)
            min = Math.min(min, dist(pts[i], pts[j]));
    return min;
}
```

### Visualization

```
Divide & Conquer:

     Left half    |    Right half
                  |
   *    *         |        *
      *           |   *        *
         *        |      *
   *        *     |          *
                  |
   d_L = 3.2     |    d_R = 2.8
                  |
        d = min(3.2, 2.8) = 2.8
                  |
    Strip: points within 2.8 of midline
    Only check 7 neighbors in y-sorted strip!
```

### Complexity
- Time: O(n log n) with merge-sort based approach, O(n log²n) with simpler sort
- Space: O(n)

---

## Pattern 7: Max Points on a Line

### Signal
- "Maximum number of collinear points"
- LC 149

### Template

```java
// Key insight: represent slope as reduced fraction (dy/gcd, dx/gcd)
// to avoid floating point entirely
public int maxPoints(int[][] points) {
    int n = points.length;
    if (n <= 2) return n;
    int result = 2;
    
    for (int i = 0; i < n; i++) {
        Map<Long, Integer> slopeCount = new HashMap<>();
        int duplicate = 1;
        
        for (int j = i + 1; j < n; j++) {
            int dx = points[j][0] - points[i][0];
            int dy = points[j][1] - points[i][1];
            
            if (dx == 0 && dy == 0) {
                duplicate++;
                continue;
            }
            
            // Normalize slope representation
            int g = gcd(Math.abs(dx), Math.abs(dy));
            dx /= g;
            dy /= g;
            
            // Ensure consistent sign: dx > 0, or dx == 0 && dy > 0
            if (dx < 0) { dx = -dx; dy = -dy; }
            if (dx == 0) dy = Math.abs(dy);
            
            // Pack into single long to use as key
            long key = (long) dy * 20001L + dx;  // offset to handle negatives
            slopeCount.merge(key, 1, Integer::sum);
        }
        
        int localMax = 0;
        for (int count : slopeCount.values())
            localMax = Math.max(localMax, count);
        result = Math.max(result, localMax + duplicate);
    }
    return result;
}

int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
```

### Why GCD-based slope?
```
Points: (0,0), (1,2), (2,4), (3,6)

Floating point slope: 2.0, 2.0, 2.0 — works here
But: (0,0), (94911151,94911150) — slope = 0.99999998... 
vs (0,0), (94911152,94911151) — slope = 0.99999998...
DIFFERENT lines, SAME float! 

GCD approach: (94911150/gcd, 94911151/gcd) vs (94911151/gcd, 94911152/gcd)
Always distinguishable.
```

### Complexity
- Time: O(n²)
- Space: O(n)

---

## Pattern 8: Valid Square / Rectangle Detection

### Signal
- Given 4 points, determine if they form a square/rectangle
- LC 593: Valid Square

### Template

```java
// Valid Square: all 4 sides equal + both diagonals equal + side > 0
public boolean validSquare(int[] p1, int[] p2, int[] p3, int[] p4) {
    long[] dists = new long[6];
    int[][] pts = {p1, p2, p3, p4};
    int k = 0;
    for (int i = 0; i < 4; i++)
        for (int j = i + 1; j < 4; j++)
            dists[k++] = dist2(pts[i], pts[j]);
    
    Arrays.sort(dists);
    // After sorting: 4 equal sides, then 2 equal diagonals
    // sides must be > 0, diagonals must be > sides
    return dists[0] > 0 
        && dists[0] == dists[1] && dists[1] == dists[2] && dists[2] == dists[3]
        && dists[4] == dists[5];
}

long dist2(int[] a, int[] b) {
    long dx = a[0] - b[0], dy = a[1] - b[1];
    return dx * dx + dy * dy;
}

// Valid Rectangle: check all 4 angles are 90° using dot product
// For points A,B,C,D forming rectangle:
// Find center, verify all 4 distances to center are equal
boolean validRectangle(int[] p1, int[] p2, int[] p3, int[] p4) {
    // Center of diagonals must coincide
    // And all distances from center must be equal (diagonals bisect)
    long cx = p1[0] + p3[0], cy = p1[1] + p3[1]; // 2*center
    if (cx != p2[0] + p4[0] || cy != p2[1] + p4[1]) {
        // Try other diagonal pairings
        // ... (need to check all 3 pairings)
    }
    return true; // simplified
}
```

### Complexity
- O(1) for 4 points
- O(n⁴) if checking all quadruples from n points

---

## Pattern 9: K Closest Points to Origin

### Signal
- "K closest/nearest points"
- LC 973

### Template

```java
// Approach 1: Max-Heap — O(n log k)
public int[][] kClosest_heap(int[][] points, int k) {
    // Max-heap: keep k smallest by evicting largest
    PriorityQueue<int[]> pq = new PriorityQueue<>(
        (a, b) -> (b[0]*b[0] + b[1]*b[1]) - (a[0]*a[0] + a[1]*a[1])
    );
    for (int[] p : points) {
        pq.offer(p);
        if (pq.size() > k) pq.poll();
    }
    return pq.toArray(new int[k][]);
}

// Approach 2: Quickselect — O(n) average, O(n²) worst
public int[][] kClosest_quickselect(int[][] points, int k) {
    quickselect(points, 0, points.length - 1, k);
    return Arrays.copyOf(points, k);
}

void quickselect(int[][] pts, int lo, int hi, int k) {
    if (lo >= hi) return;
    int pivot = partition(pts, lo, hi);
    if (pivot == k) return;
    else if (pivot < k) quickselect(pts, pivot + 1, hi, k);
    else quickselect(pts, lo, pivot - 1, k);
}

int partition(int[][] pts, int lo, int hi) {
    int[] pivot = pts[hi];
    long pivotDist = dist2(pivot);
    int i = lo;
    for (int j = lo; j < hi; j++) {
        if (dist2(pts[j]) <= pivotDist) {
            int[] tmp = pts[i]; pts[i] = pts[j]; pts[j] = tmp;
            i++;
        }
    }
    int[] tmp = pts[i]; pts[i] = pts[hi]; pts[hi] = tmp;
    return i;
}

long dist2(int[] p) { return (long)p[0]*p[0] + (long)p[1]*p[1]; }
```

### When to Use Which

| Approach | Time | Space | When |
|----------|------|-------|------|
| Max-Heap | O(n log k) | O(k) | Streaming, k << n |
| Quickselect | O(n) avg | O(1) | All data available, need speed |
| Sort | O(n log n) | O(n) | Simple, n is small |

### Complexity
- Heap: O(n log k) time, O(k) space
- Quickselect: O(n) average, O(n²) worst, O(1) extra space

---

## Pattern 10: Minimum Area Rectangle

### Signal
- "Smallest rectangle formed by points"
- LC 939: Minimum Area Rectangle

### Template

```java
// Key insight: enumerate DIAGONAL pairs, check if other 2 corners exist
// Two points form a diagonal iff the other two corners are in our point set
public int minAreaRect(int[][] points) {
    Set<Long> pointSet = new HashSet<>();
    for (int[] p : points)
        pointSet.add(encode(p[0], p[1]));
    
    int min = Integer.MAX_VALUE;
    int n = points.length;
    
    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            int x1 = points[i][0], y1 = points[i][1];
            int x2 = points[j][0], y2 = points[j][1];
            
            // These two points must have different x AND different y
            // to form opposite corners of axis-aligned rectangle
            if (x1 == x2 || y1 == y2) continue;
            
            // Check if the other two corners exist
            if (pointSet.contains(encode(x1, y2)) && 
                pointSet.contains(encode(x2, y1))) {
                min = Math.min(min, Math.abs(x2 - x1) * Math.abs(y2 - y1));
            }
        }
    }
    return min == Integer.MAX_VALUE ? 0 : min;
}

long encode(int x, int y) {
    return (long) x * 40001L + y;  // offset for coordinate range
}
```

### For arbitrary (non-axis-aligned) rectangles (LC 963):

```java
// Enumerate pairs as DIAGONALS of rectangle
// Two points are diagonal iff they share the same center and same distance to center
// Group by (center, half-diagonal-length), then check pairs within each group
public double minAreaFreeRect(int[][] points) {
    Set<Long> set = new HashSet<>();
    for (int[] p : points) set.add(encode(p[0], p[1]));
    
    double min = Double.MAX_VALUE;
    int n = points.length;
    
    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            // (i,j) and (i,k) are adjacent edges from point i
            for (int k = j + 1; k < n; k++) {
                // Check if i,j,k form a right angle at i
                int dx1 = points[j][0] - points[i][0];
                int dy1 = points[j][1] - points[i][1];
                int dx2 = points[k][0] - points[i][0];
                int dy2 = points[k][1] - points[i][1];
                
                if (dx1 * dx2 + dy1 * dy2 != 0) continue; // not 90°
                
                // Fourth point
                int fx = points[j][0] + dx2, fy = points[j][1] + dy2;
                if (set.contains(encode(fx, fy))) {
                    double area = Math.sqrt(dx1*dx1+dy1*dy1) * Math.sqrt(dx2*dx2+dy2*dy2);
                    min = Math.min(min, area);
                }
            }
        }
    }
    return min == Double.MAX_VALUE ? 0 : min;
}
```

### Complexity
- Axis-aligned: O(n²) time, O(n) space
- Arbitrary: O(n³) time, O(n) space

---

## Pattern 11: Erect the Fence (Convex Hull Application)

### Signal
- LC 587: "Erect the Fence"
- Convex hull BUT must include all points on the boundary (collinear edge points)

### Template

```java
// Modified Andrew's Monotone Chain that includes collinear boundary points
public int[][] outerTrees(int[][] trees) {
    int n = trees.length;
    if (n <= 3) return trees;
    
    Arrays.sort(trees, (a, b) -> a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
    
    Set<List<Integer>> result = new HashSet<>();
    int[][] hull = new int[2 * n][];
    int k = 0;
    
    // Lower hull — use <= 0 to exclude collinear-interior, BUT...
    // Actually for "include boundary": use < 0 (strict) to build hull,
    // then the last edge's collinear points are missed.
    // Trick: for upper hull's last segment, reverse-sort collinear points.
    
    // Simpler approach: use < 0, then add collinear points on each edge
    // Cleanest: use Andrew's with < 0, result is the hull.
    // Then for each edge of hull, add all original points that lie on it.
    
    // Standard approach for this problem:
    for (int i = 0; i < n; i++) {
        while (k >= 2 && cross(hull[k-2], hull[k-1], trees[i]) < 0) k--;
        hull[k++] = trees[i];
    }
    // Upper hull (note: use < 0 not <= 0)
    int lower = k + 1;
    for (int i = n - 2; i >= 0; i--) {
        while (k >= lower && cross(hull[k-2], hull[k-1], trees[i]) < 0) k--;
        hull[k++] = trees[i];
    }
    
    // Collect unique points (handles collinear on edges)
    // But wait — this ALREADY includes collinear points with < 0!
    // Because < 0 means: only remove if CLOCKWISE. Collinear points (==0) are KEPT.
    
    // Actually re-read: while cross < 0 → remove. So if cross == 0, we DON'T remove.
    // That means collinear points ARE included. Perfect for this problem.
    
    Set<List<Integer>> unique = new HashSet<>();
    for (int i = 0; i < k - 1; i++)
        unique.add(Arrays.asList(hull[i][0], hull[i][1]));
    
    int[][] res = new int[unique.size()][2];
    int idx = 0;
    for (List<Integer> p : unique)
        res[idx++] = new int[]{p.get(0), p.get(1)};
    return res;
}
```

### Key Difference from Standard Convex Hull
- Standard hull: `cross <= 0` removes collinear points (gives minimal vertices)
- Erect the Fence: `cross < 0` keeps collinear points on boundary edges

### Complexity
- Time: O(n log n)
- Space: O(n)

---

## Pattern 12: Robot Return to Origin / Bounded in Circle

### Signal
- LC 657: Robot Return to Origin
- LC 1041: Robot Bounded in a Circle
- Simulate movement, check periodic behavior

### Template

```java
// LC 657: Robot Return to Origin — trivial
public boolean judgeCircle(String moves) {
    int x = 0, y = 0;
    for (char c : moves.toCharArray()) {
        if (c == 'U') y++;
        else if (c == 'D') y--;
        else if (c == 'L') x--;
        else x++;
    }
    return x == 0 && y == 0;
}

// LC 1041: Robot Bounded In Circle
// Key insight: after ONE execution of instructions,
// robot is bounded iff:
//   1. It returns to origin, OR
//   2. It's NOT facing north (will cycle back in 2 or 4 repetitions)
public boolean isRobotBounded(String instructions) {
    int x = 0, y = 0;
    int dir = 0; // 0=N, 1=E, 2=S, 3=W
    int[][] moves = {{0,1}, {1,0}, {0,-1}, {-1,0}};
    
    for (char c : instructions.toCharArray()) {
        if (c == 'G') {
            x += moves[dir][0];
            y += moves[dir][1];
        } else if (c == 'L') {
            dir = (dir + 3) % 4;
        } else { // R
            dir = (dir + 1) % 4;
        }
    }
    
    // Bounded if back at origin OR not facing north
    return (x == 0 && y == 0) || dir != 0;
}
```

### Why "not facing north" means bounded

```
After 1 cycle:        After 4 cycles (at most):

Facing East:          Repeats 4x, traces a square-ish path
  →                     → ↑ ← ↓  (back to start)
  
Facing South:         Repeats 2x:
  ↓                     ↓ ↑  (back to start)

Facing West:          Repeats 4x:
  ←                     ← ↓ → ↑  (back to start)

Facing North + not at origin:
  ↑↑↑↑...             Drifts forever. UNBOUNDED.
```

### Complexity
- O(n) where n = instruction length

---

## Summary Table

| # | Pattern | Key Technique | Time | Pitfall |
|---|---------|--------------|------|---------|
| 1 | Distance | Compare squared, avoid sqrt | O(1) | int overflow → use long |
| 2 | Cross Product | `(A-O)×(B-O)` | O(1) | Sign convention (CW vs CCW) |
| 3 | Convex Hull | Sort + monotone chain | O(n log n) | Collinear point handling |
| 4 | Line Intersection | Orientation + straddle | O(1) | Collinear overlap edge case |
| 5 | Point in Polygon | Ray casting (odd/even) | O(n) | Point on edge = boundary |
| 6 | Closest Pair | Divide & conquer + strip | O(n log n) | Strip only checks 7 neighbors |
| 7 | Max Points on Line | GCD-normalized slope | O(n²) | NEVER use floating point slope |
| 8 | Valid Square | Sort 6 distances | O(1) | Degenerate (zero-area) |
| 9 | K Closest | Heap or Quickselect | O(n)/O(n log k) | Don't sqrt for comparison |
| 10 | Min Area Rect | HashSet + corner check | O(n²) | Axis-aligned vs arbitrary |
| 11 | Erect the Fence | Convex hull (keep collinear) | O(n log n) | `< 0` not `<= 0` |
| 12 | Robot Bounded | Simulate + direction check | O(n) | Not-north ⟹ bounded |

---

## Interview Tips

1. **Always ask**: "Are coordinates integers?" — if yes, avoid all floating point
2. **Overflow**: `int × int` can overflow. Use `long` for cross products and distance²
3. **Collinear points**: The #1 source of bugs in hull/intersection problems
4. **Don't implement from scratch** unless asked — know which library functions exist
5. **Simplify first**: Many "geometry" problems reduce to sorting or hashing after the right transformation (e.g., Manhattan → sorted coordinates, slope → GCD pair)

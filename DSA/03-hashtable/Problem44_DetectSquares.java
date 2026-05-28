import java.util.*;

/**
 * Problem 44: Detect Squares
 * Design a data structure to add points and count axis-aligned squares given a query point.
 *
 * Approach: Store point counts in HashMap. For query point p1, iterate all points p3
 * with same x as p1. Then check if p2 and p4 exist to form square.
 *
 * Time Complexity: O(n) per count query
 * Space Complexity: O(n)
 *
 * Production Analogy: Like spatial indexing in geofencing - detecting rectangular
 * zones from known boundary points.
 */
public class Problem44_DetectSquares {
    private Map<String, Integer> pointCount = new HashMap<>();
    private List<int[]> points = new ArrayList<>();

    public void add(int[] point) {
        String key = point[0] + "," + point[1];
        pointCount.merge(key, 1, Integer::sum);
        points.add(point);
    }

    public int count(int[] point) {
        int px = point[0], py = point[1], total = 0;
        for (int[] p : points) {
            int qx = p[0], qy = p[1];
            if (Math.abs(px - qx) != Math.abs(py - qy) || px == qx || py == qy) continue;
            total += pointCount.getOrDefault(px + "," + qy, 0) *
                     pointCount.getOrDefault(qx + "," + py, 0);
        }
        return total;
    }

    public static void main(String[] args) {
        Problem44_DetectSquares ds = new Problem44_DetectSquares();
        ds.add(new int[]{3,10}); ds.add(new int[]{11,2}); ds.add(new int[]{3,2});
        System.out.println(ds.count(new int[]{11,10})); // 1
        System.out.println(ds.count(new int[]{14,8})); // 0
        ds.add(new int[]{11,2});
        System.out.println(ds.count(new int[]{11,10})); // 2
    }
}

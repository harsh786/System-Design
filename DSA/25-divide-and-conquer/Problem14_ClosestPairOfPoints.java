import java.util.*;

/**
 * Problem 14: Closest Pair of Points
 * 
 * D&C Approach:
 * - DIVIDE: Sort by x, split at median x-coordinate
 * - CONQUER: Find closest pair in left and right halves
 * - COMBINE: Check strip of width 2*delta around dividing line
 *   Key insight: only need to check at most 7 points ahead in strip (sorted by y)
 * 
 * Time: O(n log n), Space: O(n)
 * Naive: O(n^2), D&C brings it to O(n log n)
 * 
 * Production Analogy:
 * - Nearest neighbor search in geospatial databases
 * - Finding closest servers in CDN routing
 * - Collision detection in physics engines
 */
public class Problem14_ClosestPairOfPoints {

    static double closestPair(int[][] points) {
        int[][] sorted = points.clone();
        Arrays.sort(sorted, (a, b) -> a[0] - b[0]);
        return closest(sorted, 0, sorted.length - 1);
    }

    static double closest(int[][] pts, int lo, int hi) {
        if (hi - lo < 3) {
            return bruteForce(pts, lo, hi);
        }
        int mid = lo + (hi - lo) / 2;
        int midX = pts[mid][0];
        
        double dl = closest(pts, lo, mid);
        double dr = closest(pts, mid + 1, hi);
        double d = Math.min(dl, dr);
        
        // Build strip
        List<int[]> strip = new ArrayList<>();
        for (int i = lo; i <= hi; i++) {
            if (Math.abs(pts[i][0] - midX) < d) strip.add(pts[i]);
        }
        strip.sort((a, b) -> a[1] - b[1]);
        
        // Check strip - at most 7 comparisons per point
        for (int i = 0; i < strip.size(); i++) {
            for (int j = i + 1; j < strip.size() && (strip.get(j)[1] - strip.get(i)[1]) < d; j++) {
                d = Math.min(d, dist(strip.get(i), strip.get(j)));
            }
        }
        return d;
    }

    static double bruteForce(int[][] pts, int lo, int hi) {
        double min = Double.MAX_VALUE;
        for (int i = lo; i <= hi; i++)
            for (int j = i + 1; j <= hi; j++)
                min = Math.min(min, dist(pts[i], pts[j]));
        return min;
    }

    static double dist(int[] a, int[] b) {
        return Math.sqrt((long)(a[0]-b[0])*(a[0]-b[0]) + (long)(a[1]-b[1])*(a[1]-b[1]));
    }

    public static void main(String[] args) {
        System.out.printf("%.4f%n", closestPair(new int[][]{{0,0},{1,1},{2,2},{3,3}})); // 1.4142
        System.out.printf("%.4f%n", closestPair(new int[][]{{0,0},{3,4},{1,0}})); // 1.0
        System.out.printf("%.4f%n", closestPair(new int[][]{{-1,0},{0,0},{1,0}})); // 1.0
        System.out.printf("%.4f%n", closestPair(new int[][]{{0,0},{100,100},{50,50},{25,25}})); // 35.3553
    }
}

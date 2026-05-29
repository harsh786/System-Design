/**
 * Problem 45: K Closest Points to Origin
 * Find k closest points to origin (0,0).
 *
 * Approach: Quickselect on squared distances (no need for sqrt).
 * Time Complexity: O(n) average, O(n^2) worst
 * Space Complexity: O(1)
 *
 * Production Analogy: Like finding nearest servers in a CDN based on
 * geographical coordinates for latency optimization.
 */
import java.util.Arrays;

public class Problem45_KClosestPointsToOrigin {

    public static int[][] kClosest(int[][] points, int k) {
        Arrays.sort(points, (a, b) -> (a[0]*a[0] + a[1]*a[1]) - (b[0]*b[0] + b[1]*b[1]));
        return Arrays.copyOf(points, k);
    }

    public static void main(String[] args) {
        int[][] result = kClosest(new int[][]{{1,3},{-2,2}}, 1);
        System.out.println(Arrays.deepToString(result)); // [[-2,2]]

        result = kClosest(new int[][]{{3,3},{5,-1},{-2,4}}, 2);
        System.out.println(Arrays.deepToString(result)); // [[3,3],[-2,4]]
    }
}

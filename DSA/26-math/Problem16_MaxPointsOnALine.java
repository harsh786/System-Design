/**
 * Problem 16: Max Points on a Line
 * Given points on a 2D plane, find the max number of points on the same line.
 *
 * Approach: For each point, compute slope to all others using GCD-reduced fractions.
 * Time Complexity: O(n^2)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like detecting collinear sensor readings for anomaly
 * detection in IoT data streams.
 */
import java.util.HashMap;
import java.util.Map;

public class Problem16_MaxPointsOnALine {

    public static int maxPoints(int[][] points) {
        if (points.length <= 2) return points.length;
        int max = 2;

        for (int i = 0; i < points.length; i++) {
            Map<String, Integer> slopes = new HashMap<>();
            for (int j = i + 1; j < points.length; j++) {
                int dx = points[j][0] - points[i][0];
                int dy = points[j][1] - points[i][1];
                int g = gcd(Math.abs(dx), Math.abs(dy));
                if (g != 0) { dx /= g; dy /= g; }
                if (dx < 0) { dx = -dx; dy = -dy; }
                if (dx == 0) dy = Math.abs(dy);
                String key = dx + "/" + dy;
                slopes.put(key, slopes.getOrDefault(key, 1) + 1);
                max = Math.max(max, slopes.get(key));
            }
        }
        return max;
    }

    private static int gcd(int a, int b) {
        return b == 0 ? a : gcd(b, a % b);
    }

    public static void main(String[] args) {
        System.out.println(maxPoints(new int[][]{{1,1},{2,2},{3,3}}));           // 3
        System.out.println(maxPoints(new int[][]{{1,1},{3,2},{5,3},{4,1},{2,3},{1,4}})); // 4
        System.out.println(maxPoints(new int[][]{{0,0}}));                       // 1
    }
}

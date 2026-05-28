import java.util.*;

/**
 * Problem 43: Max Points on a Line
 * Given points on a 2D plane, find max number of points on the same straight line.
 *
 * Approach: For each point, compute slopes to all other points using HashMap.
 * Use GCD to represent slope as reduced fraction to avoid floating point issues.
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like trend detection in time-series data - finding the largest
 * set of data points that follow a linear trend.
 */
public class Problem43_MaxPointsOnALine {
    public int maxPoints(int[][] points) {
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
                slopes.merge(key, 1, Integer::sum);
                max = Math.max(max, slopes.get(key) + 1);
            }
        }
        return max;
    }

    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }

    public static void main(String[] args) {
        Problem43_MaxPointsOnALine sol = new Problem43_MaxPointsOnALine();
        System.out.println(sol.maxPoints(new int[][]{{1,1},{2,2},{3,3}})); // 3
        System.out.println(sol.maxPoints(new int[][]{{1,1},{3,2},{5,3},{4,1},{2,3},{1,4}})); // 4
    }
}

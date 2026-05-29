package numbertheory;

import java.util.*;

/**
 * Problem 33: Max Points on a Line (LeetCode 149) using GCD for slope representation
 * 
 * Approach: For each point, compute slope to all others as reduced fraction (dy/gcd, dx/gcd).
 * 
 * Time Complexity: O(n^2)
 * Space Complexity: O(n)
 */
public class Problem33_MaxPointsOnALine {
    
    public int maxPoints(int[][] points) {
        int n = points.length, ans = 1;
        for (int i = 0; i < n; i++) {
            Map<String, Integer> map = new HashMap<>();
            for (int j = i + 1; j < n; j++) {
                int dx = points[j][0] - points[i][0];
                int dy = points[j][1] - points[i][1];
                int g = gcd(Math.abs(dx), Math.abs(dy));
                if (g != 0) { dx /= g; dy /= g; }
                if (dx < 0) { dx = -dx; dy = -dy; }
                if (dx == 0) dy = Math.abs(dy);
                String key = dx + "," + dy;
                map.merge(key, 1, Integer::sum);
                ans = Math.max(ans, map.get(key) + 1);
            }
        }
        return ans;
    }
    
    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    
    public static void main(String[] args) {
        Problem33_MaxPointsOnALine sol = new Problem33_MaxPointsOnALine();
        System.out.println(sol.maxPoints(new int[][]{{1,1},{2,2},{3,3}})); // 3
        System.out.println(sol.maxPoints(new int[][]{{1,1},{3,2},{5,3},{4,1},{2,3},{1,4}})); // 4
    }
}

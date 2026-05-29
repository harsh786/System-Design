import java.util.*;

public class Problem01_MaxPointsOnALine {
    public static int maxPoints(int[][] points) {
        int n = points.length, max = 1;
        for (int i = 0; i < n; i++) {
            Map<String, Integer> map = new HashMap<>();
            for (int j = i + 1; j < n; j++) {
                int dx = points[j][0] - points[i][0], dy = points[j][1] - points[i][1];
                int g = gcd(Math.abs(dx), Math.abs(dy));
                if (g != 0) { dx /= g; dy /= g; }
                if (dx < 0) { dx = -dx; dy = -dy; } else if (dx == 0) dy = Math.abs(dy);
                String key = dx + "," + dy;
                map.merge(key, 1, Integer::sum);
                max = Math.max(max, map.get(key) + 1);
            }
        }
        return max;
    }
    static int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    public static void main(String[] args) {
        System.out.println(maxPoints(new int[][]{{1,1},{2,2},{3,3}})); // 3
    }
}

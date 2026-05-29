import java.util.*;

public class Problem18_MaxPointsOnALine {
    public int maxPoints(int[][] points) {
        int n = points.length, max = 1;
        for (int i = 0; i < n; i++) {
            Map<String, Integer> slopes = new HashMap<>();
            for (int j = i + 1; j < n; j++) {
                int dx = points[j][0] - points[i][0], dy = points[j][1] - points[i][1];
                int g = gcd(Math.abs(dx), Math.abs(dy));
                if (g != 0) { dx /= g; dy /= g; }
                if (dx < 0) { dx = -dx; dy = -dy; }
                if (dx == 0) dy = 1;
                String key = dx + "/" + dy;
                slopes.merge(key, 1, Integer::sum);
                max = Math.max(max, slopes.get(key) + 1);
            }
        }
        return max;
    }

    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }

    public static void main(String[] args) {
        Problem18_MaxPointsOnALine sol = new Problem18_MaxPointsOnALine();
        System.out.println(sol.maxPoints(new int[][]{{1,1},{2,2},{3,3}})); // 3
    }
}

import java.util.*;

public class Problem05_MinimumAreaRectangle {
    public static int minAreaRect(int[][] points) {
        Set<String> set = new HashSet<>();
        for (int[] p : points) set.add(p[0] + "," + p[1]);
        int min = Integer.MAX_VALUE;
        for (int i = 0; i < points.length; i++) for (int j = i + 1; j < points.length; j++) {
            int x1 = points[i][0], y1 = points[i][1], x2 = points[j][0], y2 = points[j][1];
            if (x1 == x2 || y1 == y2) continue;
            if (set.contains(x1 + "," + y2) && set.contains(x2 + "," + y1))
                min = Math.min(min, Math.abs(x2 - x1) * Math.abs(y2 - y1));
        }
        return min == Integer.MAX_VALUE ? 0 : min;
    }
    public static void main(String[] args) {
        System.out.println(minAreaRect(new int[][]{{1,1},{1,3},{3,1},{3,3},{2,2}})); // 4
    }
}

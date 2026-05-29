import java.util.*;

public class Problem20_MinimumAreaRectangleII {
    public static double minAreaFreeRect(int[][] points) {
        int n = points.length;
        double min = Double.MAX_VALUE;
        Map<String, List<int[]>> map = new HashMap<>();
        for (int i = 0; i < n; i++) for (int j = i+1; j < n; j++) {
            long cx = points[i][0] + points[j][0], cy = points[i][1] + points[j][1];
            long dist = (long)(points[i][0]-points[j][0])*(points[i][0]-points[j][0]) + (long)(points[i][1]-points[j][1])*(points[i][1]-points[j][1]);
            String key = cx + "," + cy + "," + dist;
            map.computeIfAbsent(key, k -> new ArrayList<>()).add(new int[]{i, j});
        }
        for (List<int[]> pairs : map.values()) {
            for (int i = 0; i < pairs.size(); i++) for (int j = i+1; j < pairs.size(); j++) {
                int[] p1 = points[pairs.get(i)[0]], p2 = points[pairs.get(j)[0]], p3 = points[pairs.get(j)[1]];
                double d1 = Math.sqrt((p1[0]-p2[0])*(p1[0]-p2[0])+(p1[1]-p2[1])*(p1[1]-p2[1]));
                double d2 = Math.sqrt((p1[0]-p3[0])*(p1[0]-p3[0])+(p1[1]-p3[1])*(p1[1]-p3[1]));
                min = Math.min(min, d1 * d2);
            }
        }
        return min == Double.MAX_VALUE ? 0 : min;
    }
    public static void main(String[] args) {
        System.out.println(minAreaFreeRect(new int[][]{{1,2},{2,1},{1,0},{0,1}})); // 2.0
    }
}

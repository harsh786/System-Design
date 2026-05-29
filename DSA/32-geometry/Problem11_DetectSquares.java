import java.util.*;

public class Problem11_DetectSquares {
    Map<String, Integer> counts = new HashMap<>();
    List<int[]> points = new ArrayList<>();
    public void add(int[] point) {
        String key = point[0] + "," + point[1];
        counts.merge(key, 1, Integer::sum);
        points.add(point);
    }
    public int count(int[] point) {
        int total = 0;
        int px = point[0], py = point[1];
        for (int[] p : points) {
            int x = p[0], y = p[1];
            if (Math.abs(px - x) == 0 || Math.abs(px - x) != Math.abs(py - y)) continue;
            total += counts.getOrDefault(px + "," + y, 0) * counts.getOrDefault(x + "," + py, 0);
        }
        return total;
    }
    public static void main(String[] args) {
        Problem11_DetectSquares ds = new Problem11_DetectSquares();
        ds.add(new int[]{3,10}); ds.add(new int[]{11,2}); ds.add(new int[]{3,2});
        System.out.println(ds.count(new int[]{11,10})); // 1
    }
}

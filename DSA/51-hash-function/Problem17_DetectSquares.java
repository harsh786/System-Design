import java.util.*;

public class Problem17_DetectSquares {
    private Map<String, Integer> pointCount = new HashMap<>();
    private List<int[]> points = new ArrayList<>();

    public void add(int[] point) {
        String key = point[0] + "," + point[1];
        pointCount.merge(key, 1, Integer::sum);
        points.add(point);
    }

    public int count(int[] point) {
        int px = point[0], py = point[1], total = 0;
        for (int[] p : points) {
            int x = p[0], y = p[1];
            if (Math.abs(px - x) != Math.abs(py - y) || px == x && py == y) continue;
            total += pointCount.getOrDefault(px + "," + y, 0) * pointCount.getOrDefault(x + "," + py, 0);
        }
        return total;
    }

    public static void main(String[] args) {
        Problem17_DetectSquares sol = new Problem17_DetectSquares();
        sol.add(new int[]{3,10}); sol.add(new int[]{11,2}); sol.add(new int[]{3,2});
        System.out.println(sol.count(new int[]{11,10})); // 1
    }
}

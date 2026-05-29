import java.util.*;

public class Problem17_ClosestPairOfPoints {
    public static double closestPair(int[][] points) {
        Arrays.sort(points, (a, b) -> a[0] - b[0]);
        return closest(points, 0, points.length - 1);
    }
    static double closest(int[][] pts, int l, int r) {
        if (r - l < 3) {
            double min = Double.MAX_VALUE;
            for (int i = l; i <= r; i++) for (int j = i+1; j <= r; j++) min = Math.min(min, dist(pts[i], pts[j]));
            return min;
        }
        int mid = (l + r) / 2;
        double d = Math.min(closest(pts, l, mid), closest(pts, mid+1, r));
        List<int[]> strip = new ArrayList<>();
        for (int i = l; i <= r; i++) if (Math.abs(pts[i][0] - pts[mid][0]) < d) strip.add(pts[i]);
        strip.sort((a, b) -> a[1] - b[1]);
        for (int i = 0; i < strip.size(); i++)
            for (int j = i+1; j < strip.size() && strip.get(j)[1] - strip.get(i)[1] < d; j++)
                d = Math.min(d, dist(strip.get(i), strip.get(j)));
        return d;
    }
    static double dist(int[] a, int[] b) { return Math.sqrt((long)(a[0]-b[0])*(a[0]-b[0]) + (long)(a[1]-b[1])*(a[1]-b[1])); }
    public static void main(String[] args) {
        System.out.printf("%.4f%n", closestPair(new int[][]{{0,0},{1,1},{2,2},{3,3},{1,2}}));
    }
}

import java.util.*;

public class Problem41_LineSweepClosestPair {
    public static double closestPair(int[][] points) {
        Arrays.sort(points, (a, b) -> a[0] - b[0]);
        TreeSet<int[]> active = new TreeSet<>((a, b) -> a[1] != b[1] ? a[1] - b[1] : a[0] - b[0]);
        double best = Double.MAX_VALUE;
        int left = 0;
        for (int[] p : points) {
            while (left < points.length && p[0] - points[left][0] > best) { active.remove(points[left]); left++; }
            int[] lo = {Integer.MIN_VALUE, (int)(p[1] - best)};
            int[] hi = {Integer.MAX_VALUE, (int)(p[1] + best)};
            for (int[] q : active.subSet(lo, true, hi, true)) {
                double d = Math.sqrt((long)(p[0]-q[0])*(p[0]-q[0]) + (long)(p[1]-q[1])*(p[1]-q[1]));
                best = Math.min(best, d);
            }
            active.add(p);
        }
        return best;
    }
    public static void main(String[] args) {
        System.out.printf("%.4f%n", closestPair(new int[][]{{0,0},{3,4},{1,1},{5,5}}));
    }
}

import java.util.*;

public class Problem37_SweepLineClosestPoints {
    public double closestDistance(int[][] points) {
        Arrays.sort(points, (a, b) -> a[0] - b[0]);
        double d = Double.MAX_VALUE;
        TreeSet<int[]> active = new TreeSet<>((a, b) -> a[1] != b[1] ? a[1] - b[1] : a[0] - b[0]);
        int j = 0;
        for (int i = 0; i < points.length; i++) {
            while (j < i && points[i][0] - points[j][0] > d) { active.remove(points[j++]); }
            for (int[] p : active.subSet(new int[]{Integer.MIN_VALUE, (int)(points[i][1] - d) - 1}, 
                    new int[]{Integer.MAX_VALUE, (int)(points[i][1] + d) + 1})) {
                double dist = Math.hypot(points[i][0] - p[0], points[i][1] - p[1]);
                d = Math.min(d, dist);
            }
            active.add(points[i]);
        }
        return d;
    }

    public static void main(String[] args) {
        Problem37_SweepLineClosestPoints sol = new Problem37_SweepLineClosestPoints();
        System.out.printf("%.4f%n", sol.closestDistance(new int[][]{{0,0},{3,4},{1,1},{5,5}}));
    }
}

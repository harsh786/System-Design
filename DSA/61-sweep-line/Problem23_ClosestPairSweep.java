import java.util.*;

public class Problem23_ClosestPairSweep {
    public double closestPair(int[][] points) {
        Arrays.sort(points, (a, b) -> a[0] - b[0]);
        TreeSet<int[]> active = new TreeSet<>((a, b) -> a[1] != b[1] ? a[1] - b[1] : a[0] - b[0]);
        double minDist = Double.MAX_VALUE;
        int j = 0;
        for (int i = 0; i < points.length; i++) {
            while (j < i && points[i][0] - points[j][0] > minDist) { active.remove(points[j]); j++; }
            int[] lo = {Integer.MIN_VALUE, (int)(points[i][1] - minDist)};
            int[] hi = {Integer.MAX_VALUE, (int)(points[i][1] + minDist)};
            for (int[] p : active.subSet(lo, false, hi, false)) {
                double d = Math.sqrt(Math.pow(points[i][0]-p[0],2) + Math.pow(points[i][1]-p[1],2));
                minDist = Math.min(minDist, d);
            }
            active.add(points[i]);
        }
        return minDist;
    }

    public static void main(String[] args) {
        Problem23_ClosestPairSweep sol = new Problem23_ClosestPairSweep();
        System.out.println(sol.closestPair(new int[][]{{0,0},{1,1},{2,2},{3,3},{1,0}}));
    }
}

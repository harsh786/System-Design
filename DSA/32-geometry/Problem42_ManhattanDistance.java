import java.util.*;

public class Problem42_ManhattanDistance {
    // Find pair with max Manhattan distance
    public static int maxManhattanDistance(int[][] points) {
        // |xi-xj| + |yi-yj| = max of (xi+yi)-(xj+yj), (xi-yi)-(xj-yj), etc.
        int maxSum = Integer.MIN_VALUE, minSum = Integer.MAX_VALUE;
        int maxDiff = Integer.MIN_VALUE, minDiff = Integer.MAX_VALUE;
        for (int[] p : points) {
            maxSum = Math.max(maxSum, p[0]+p[1]); minSum = Math.min(minSum, p[0]+p[1]);
            maxDiff = Math.max(maxDiff, p[0]-p[1]); minDiff = Math.min(minDiff, p[0]-p[1]);
        }
        return Math.max(maxSum - minSum, maxDiff - minDiff);
    }
    // Min Manhattan distance to all points from any cell (1D median trick)
    public static int minTotalManhattan(int[][] points) {
        int n = points.length;
        int[] xs = new int[n], ys = new int[n];
        for (int i = 0; i < n; i++) { xs[i] = points[i][0]; ys[i] = points[i][1]; }
        Arrays.sort(xs); Arrays.sort(ys);
        int medX = xs[n/2], medY = ys[n/2], total = 0;
        for (int i = 0; i < n; i++) total += Math.abs(xs[i]-medX) + Math.abs(ys[i]-medY);
        return total;
    }
    public static void main(String[] args) {
        System.out.println(maxManhattanDistance(new int[][]{{1,2},{3,4},{5,1}})); // 5
        System.out.println(minTotalManhattan(new int[][]{{0,0},{1,1},{2,2}})); // 4
    }
}

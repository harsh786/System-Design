import java.util.*;

public class Problem41_SweepLineKthNearestPoint {
    public int kthNearest(int[][] points, int[] query, int k) {
        int[] dists = new int[points.length];
        for (int i = 0; i < points.length; i++) dists[i] = Math.abs(points[i][0]-query[0]) + Math.abs(points[i][1]-query[1]);
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        for (int d : dists) { maxHeap.offer(d); if (maxHeap.size() > k) maxHeap.poll(); }
        return maxHeap.peek();
    }

    public static void main(String[] args) {
        Problem41_SweepLineKthNearestPoint sol = new Problem41_SweepLineKthNearestPoint();
        System.out.println(sol.kthNearest(new int[][]{{0,0},{1,1},{2,2},{3,3},{4,4}}, new int[]{2,2}, 2));
    }
}

import java.util.*;

public class Problem07_KClosestPointsToOrigin {
    public static int[][] kClosest(int[][] points, int k) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> (b[0]*b[0]+b[1]*b[1]) - (a[0]*a[0]+a[1]*a[1]));
        for (int[] p : points) { pq.offer(p); if (pq.size() > k) pq.poll(); }
        return pq.toArray(new int[0][]);
    }
    public static void main(String[] args) {
        int[][] res = kClosest(new int[][]{{3,3},{5,-1},{-2,4}}, 2);
        for (int[] p : res) System.out.println(Arrays.toString(p));
    }
}

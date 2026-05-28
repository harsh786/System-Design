import java.util.*;

/**
 * Problem 6: K Closest Points to Origin (LeetCode 973)
 * 
 * Approach: Max-heap of size K based on distance. Keep only K closest.
 * 
 * Time Complexity: O(N log K)
 * Space Complexity: O(K)
 * 
 * Production Analogy: Geospatial queries - finding K nearest warehouses to a
 * delivery address for logistics optimization.
 */
public class Problem06_KClosestPointsToOrigin {
    
    public int[][] kClosest(int[][] points, int k) {
        PriorityQueue<int[]> maxHeap = new PriorityQueue<>(
            (a, b) -> (b[0]*b[0] + b[1]*b[1]) - (a[0]*a[0] + a[1]*a[1]));
        
        for (int[] p : points) {
            maxHeap.offer(p);
            if (maxHeap.size() > k) maxHeap.poll();
        }
        return maxHeap.toArray(new int[k][2]);
    }
    
    public static void main(String[] args) {
        Problem06_KClosestPointsToOrigin sol = new Problem06_KClosestPointsToOrigin();
        int[][] res = sol.kClosest(new int[][]{{1,3},{-2,2},{3,3},{5,-1},{-2,4}}, 2);
        for (int[] p : res) System.out.println(Arrays.toString(p));
        System.out.println("---");
        res = sol.kClosest(new int[][]{{0,0},{1,1}}, 1);
        for (int[] p : res) System.out.println(Arrays.toString(p)); // [0,0]
    }
}

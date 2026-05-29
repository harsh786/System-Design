import java.util.*;

/**
 * Problem 33: K Closest Points to Origin
 * 
 * Return k closest points to origin (0,0).
 * 
 * Approach: QuickSelect on distance, or max-heap of size k.
 * Time Complexity: O(n) average with QuickSelect
 * Space Complexity: O(1) for QuickSelect
 * 
 * Production Analogy: Geo-proximity search - finding k nearest restaurants/drivers
 * to a user's location in ride-sharing or food delivery apps.
 */
public class Problem33_KClosestPointsToOrigin {
    
    public int[][] kClosest(int[][] points, int k) {
        // Max-heap approach
        PriorityQueue<int[]> pq = new PriorityQueue<>(
            (a, b) -> (b[0]*b[0] + b[1]*b[1]) - (a[0]*a[0] + a[1]*a[1])
        );
        
        for (int[] p : points) {
            pq.offer(p);
            if (pq.size() > k) pq.poll();
        }
        
        int[][] result = new int[k][2];
        int i = 0;
        for (int[] p : pq) result[i++] = p;
        return result;
    }
    
    public static void main(String[] args) {
        Problem33_KClosestPointsToOrigin sol = new Problem33_KClosestPointsToOrigin();
        
        System.out.println("Test 1: " + Arrays.deepToString(sol.kClosest(new int[][]{{1,3},{-2,2}}, 1))); // [[-2,2]]
        System.out.println("Test 2: " + Arrays.deepToString(sol.kClosest(new int[][]{{3,3},{5,-1},{-2,4}}, 2))); // [[3,3],[-2,4]]
        System.out.println("Test 3: " + Arrays.deepToString(sol.kClosest(new int[][]{{0,1},{1,0}}, 2))); // [[0,1],[1,0]]
    }
}

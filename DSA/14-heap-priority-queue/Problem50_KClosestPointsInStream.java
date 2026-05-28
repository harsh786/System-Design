import java.util.*;

/**
 * Problem 50: K Closest Points in Stream
 * 
 * Approach: Max-heap of size K. For each new point, compare with heap top.
 * If closer than the farthest in heap, replace.
 * 
 * Time Complexity: O(log K) per point
 * Space Complexity: O(K)
 * 
 * Production Analogy: Real-time geofencing - maintaining K nearest delivery drivers
 * to a restaurant as driver positions stream in continuously.
 */
public class Problem50_KClosestPointsInStream {
    
    private PriorityQueue<int[]> maxHeap;
    private int k;
    
    public Problem50_KClosestPointsInStream(int k) {
        this.k = k;
        this.maxHeap = new PriorityQueue<>((a, b) -> dist(b) - dist(a));
    }
    
    private int dist(int[] p) { return p[0]*p[0] + p[1]*p[1]; }
    
    public List<int[]> addPoint(int[] point) {
        maxHeap.offer(point);
        if (maxHeap.size() > k) maxHeap.poll();
        return new ArrayList<>(maxHeap);
    }
    
    public List<int[]> getKClosest() { return new ArrayList<>(maxHeap); }
    
    public static void main(String[] args) {
        Problem50_KClosestPointsInStream sol = new Problem50_KClosestPointsInStream(2);
        sol.addPoint(new int[]{3, 3});
        sol.addPoint(new int[]{1, 1});
        sol.addPoint(new int[]{5, 5});
        sol.addPoint(new int[]{2, 2});
        
        List<int[]> result = sol.getKClosest();
        System.out.print("K closest: ");
        for (int[] p : result) System.out.print(Arrays.toString(p) + " ");
        System.out.println(); // [1,1] [2,2]
        
        sol.addPoint(new int[]{0, 0});
        result = sol.getKClosest();
        System.out.print("After (0,0): ");
        for (int[] p : result) System.out.print(Arrays.toString(p) + " ");
        System.out.println(); // [0,0] [1,1]
    }
}

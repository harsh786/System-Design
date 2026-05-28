import java.util.*;

/**
 * Problem 42: Furthest Building You Can Reach (LeetCode 1642)
 * 
 * Approach: Use ladders for largest climbs (max-heap of size = ladders).
 * Use bricks for smaller climbs. Min-heap tracks ladder-allocated climbs.
 * 
 * Time Complexity: O(N log L) where L = ladders
 * Space Complexity: O(L)
 * 
 * Production Analogy: Resource allocation with premium vs standard options -
 * using premium resources (ladders) for biggest needs, standard (bricks) for smaller ones.
 */
public class Problem42_FurthestBuildingYouCanReach {
    
    public int furthestBuilding(int[] heights, int bricks, int ladders) {
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        
        for (int i = 0; i < heights.length - 1; i++) {
            int diff = heights[i + 1] - heights[i];
            if (diff <= 0) continue;
            minHeap.offer(diff);
            if (minHeap.size() > ladders) {
                bricks -= minHeap.poll();
                if (bricks < 0) return i;
            }
        }
        return heights.length - 1;
    }
    
    public static void main(String[] args) {
        Problem42_FurthestBuildingYouCanReach sol = new Problem42_FurthestBuildingYouCanReach();
        System.out.println(sol.furthestBuilding(new int[]{4,2,7,6,9,14,12}, 5, 1)); // 4
        System.out.println(sol.furthestBuilding(new int[]{4,12,2,7,3,18,20,3,19}, 10, 2)); // 7
        System.out.println(sol.furthestBuilding(new int[]{14,3,19,3}, 17, 0)); // 3
    }
}

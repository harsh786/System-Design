import java.util.*;

/**
 * Problem 24: Find K Pairs with Smallest Sums (LeetCode 373)
 * 
 * Approach: Min-heap starting with (nums1[i], nums2[0]) for all i. Expand by incrementing j.
 * 
 * Time Complexity: O(K log K)
 * Space Complexity: O(K)
 * 
 * Production Analogy: Finding cheapest product bundles by combining items from two
 * sorted price catalogs.
 */
public class Problem24_FindKPairsWithSmallestSums {
    
    public List<List<Integer>> kSmallestPairs(int[] nums1, int[] nums2, int k) {
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> (a[0] + a[1]) - (b[0] + b[1]));
        for (int i = 0; i < Math.min(k, nums1.length); i++)
            pq.offer(new int[]{nums1[i], nums2[0], 0});
        
        List<List<Integer>> result = new ArrayList<>();
        while (!pq.isEmpty() && result.size() < k) {
            int[] curr = pq.poll();
            result.add(Arrays.asList(curr[0], curr[1]));
            int j = curr[2];
            if (j + 1 < nums2.length)
                pq.offer(new int[]{curr[0], nums2[j + 1], j + 1});
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem24_FindKPairsWithSmallestSums sol = new Problem24_FindKPairsWithSmallestSums();
        System.out.println(sol.kSmallestPairs(new int[]{1,7,11}, new int[]{2,4,6}, 3));
        // [[1,2],[1,4],[1,6]]
        System.out.println(sol.kSmallestPairs(new int[]{1,1,2}, new int[]{1,2,3}, 2));
        // [[1,1],[1,1]]
    }
}

import java.util.*;

/**
 * Problem 41: Kth Smallest Prime Fraction (LeetCode 786)
 * 
 * Approach: Min-heap of fractions arr[i]/arr[j]. Start with arr[i]/arr[n-1] for all i.
 * 
 * Time Complexity: O(K log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Ranking content by engagement ratio (clicks/impressions)
 * to find the Kth lowest performing content.
 */
public class Problem41_KthSmallestPrimeFraction {
    
    public int[] kthSmallestPrimeFraction(int[] arr, int k) {
        int n = arr.length;
        // [i, j] representing arr[i]/arr[j]
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> 
            arr[a[0]] * arr[b[1]] - arr[b[0]] * arr[a[1]]);
        
        for (int i = 0; i < n - 1; i++) pq.offer(new int[]{i, n - 1});
        
        while (--k > 0) {
            int[] curr = pq.poll();
            if (curr[1] - 1 > curr[0]) pq.offer(new int[]{curr[0], curr[1] - 1});
        }
        int[] res = pq.poll();
        return new int[]{arr[res[0]], arr[res[1]]};
    }
    
    public static void main(String[] args) {
        Problem41_KthSmallestPrimeFraction sol = new Problem41_KthSmallestPrimeFraction();
        System.out.println(Arrays.toString(sol.kthSmallestPrimeFraction(new int[]{1,2,3,5}, 3))); // [2,5]
        System.out.println(Arrays.toString(sol.kthSmallestPrimeFraction(new int[]{1,7}, 1))); // [1,7]
    }
}

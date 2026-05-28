import java.util.*;

/**
 * Problem 35: Maximum Subsequence Score (LeetCode 2542)
 * 
 * Approach: Sort by nums2 descending. Use min-heap to maintain top-K nums1 values.
 * For each element as minimum of nums2, compute sum(selected nums1) * nums2[i].
 * 
 * Time Complexity: O(N log N + N log K)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Optimizing team selection where score = sum(productivity) * min(quality).
 */
public class Problem35_MaxSubsequenceScore {
    
    public long maxScore(int[] nums1, int[] nums2, int k) {
        int n = nums1.length;
        int[][] pairs = new int[n][2];
        for (int i = 0; i < n; i++) pairs[i] = new int[]{nums2[i], nums1[i]};
        Arrays.sort(pairs, (a, b) -> b[0] - a[0]);
        
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        long sum = 0, maxScore = 0;
        
        for (int[] p : pairs) {
            minHeap.offer(p[1]);
            sum += p[1];
            if (minHeap.size() > k) sum -= minHeap.poll();
            if (minHeap.size() == k) maxScore = Math.max(maxScore, sum * p[0]);
        }
        return maxScore;
    }
    
    public static void main(String[] args) {
        Problem35_MaxSubsequenceScore sol = new Problem35_MaxSubsequenceScore();
        System.out.println(sol.maxScore(new int[]{1,3,3,2}, new int[]{2,1,3,4}, 3)); // 12
        System.out.println(sol.maxScore(new int[]{4,2,3,1,1}, new int[]{7,5,10,9,6}, 1)); // 30
    }
}

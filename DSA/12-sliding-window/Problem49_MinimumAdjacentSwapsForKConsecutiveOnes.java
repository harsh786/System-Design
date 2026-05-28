import java.util.*;
/**
 * Problem 49: Minimum Adjacent Swaps for K Consecutive Ones (LeetCode 1703)
 * 
 * Approach: Collect positions of 1s. Use sliding window of size k on positions.
 * Minimum swaps = move all to median position. Use prefix sums for O(1) cost.
 * Window invariant: window of k ones-positions, compute cost to bring together.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like computing minimum data migrations to co-locate
 * k related shards onto consecutive nodes.
 */
public class Problem49_MinimumAdjacentSwapsForKConsecutiveOnes {
    public static int minMoves(int[] nums, int k) {
        // Collect indices of 1s and normalize: pos[i] -= i (to account for gaps)
        List<Long> pos = new ArrayList<>();
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] == 1) pos.add((long) i - pos.size());
        }
        int n = pos.size();
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + pos.get(i);
        
        long minCost = Long.MAX_VALUE;
        for (int i = 0; i <= n - k; i++) {
            int mid = i + k / 2;
            long median = pos.get(mid);
            // Cost = sum of |pos[j] - median| for j in [i, i+k-1]
            long leftCost = median * (mid - i) - (prefix[mid] - prefix[i]);
            long rightCost = (prefix[i + k] - prefix[mid + 1]) - median * (i + k - mid - 1);
            minCost = Math.min(minCost, leftCost + rightCost);
        }
        return (int) minCost;
    }

    public static void main(String[] args) {
        System.out.println(minMoves(new int[]{1,0,0,1,0,1}, 2));       // 1
        System.out.println(minMoves(new int[]{1,0,0,0,0,0,1,1}, 3));   // 5
        System.out.println(minMoves(new int[]{1,1,0,1}, 2));            // 0
    }
}

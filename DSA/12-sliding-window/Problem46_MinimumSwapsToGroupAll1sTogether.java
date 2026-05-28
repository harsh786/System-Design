/**
 * Problem 46: Minimum Swaps to Group All 1's Together (LeetCode 1151 / 2134)
 * 
 * Approach: Count total 1s = window size. Find window with max 1s (min 0s to swap).
 * Window invariant: fixed window of size = total ones, minimize zeros in window.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding optimal placement of hot data blocks to minimize
 * data movement in storage rebalancing.
 */
public class Problem46_MinimumSwapsToGroupAll1sTogether {
    public static int minSwaps(int[] data) {
        int totalOnes = 0;
        for (int d : data) totalOnes += d;
        if (totalOnes <= 1) return 0;
        int ones = 0;
        for (int i = 0; i < totalOnes; i++) ones += data[i];
        int maxOnes = ones;
        for (int i = totalOnes; i < data.length; i++) {
            ones += data[i] - data[i - totalOnes];
            maxOnes = Math.max(maxOnes, ones);
        }
        return totalOnes - maxOnes;
    }

    public static void main(String[] args) {
        System.out.println(minSwaps(new int[]{1,0,1,0,1}));         // 1
        System.out.println(minSwaps(new int[]{0,0,0,1,0}));         // 0
        System.out.println(minSwaps(new int[]{1,0,1,0,1,0,0,1,1,0,1})); // 3
    }
}

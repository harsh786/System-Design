import java.util.*;

/**
 * Problem 38: Closest Subsequence Sum - Meet in the Middle (LeetCode 1755)
 * 
 * D&C Approach (Meet in the Middle):
 * - DIVIDE: Split array into two halves
 * - CONQUER: Generate all possible subset sums for each half (2^(n/2) each)
 * - COMBINE: Sort one half's sums, for each sum in other half,
 *   binary search for complement closest to goal
 * 
 * Time: O(2^(n/2) * n), Space: O(2^(n/2))
 * Reduces from O(2^n) to O(2^(n/2) * log(2^(n/2)))
 * 
 * Production Analogy:
 * - Cryptanalysis (meet-in-the-middle attacks on ciphers)
 * - Resource allocation optimization with large item sets
 * - Budget optimization across many possible combinations
 */
public class Problem38_ClosestSubsequenceSum {

    public static int minAbsDifference(int[] nums, int goal) {
        int n = nums.length;
        int half = n / 2;
        
        // Generate all subset sums for both halves
        List<Integer> leftSums = generateSums(nums, 0, half);
        List<Integer> rightSums = generateSums(nums, half, n);
        
        Collections.sort(rightSums);
        
        int minDiff = Integer.MAX_VALUE;
        for (int lSum : leftSums) {
            int target = goal - lSum;
            // Binary search for closest value in rightSums
            int idx = Collections.binarySearch(rightSums, target);
            if (idx >= 0) return 0; // Exact match
            idx = -idx - 1; // Insertion point
            if (idx < rightSums.size())
                minDiff = Math.min(minDiff, Math.abs(target - rightSums.get(idx)));
            if (idx > 0)
                minDiff = Math.min(minDiff, Math.abs(target - rightSums.get(idx - 1)));
        }
        return minDiff;
    }

    private static List<Integer> generateSums(int[] nums, int start, int end) {
        List<Integer> sums = new ArrayList<>();
        sums.add(0);
        for (int i = start; i < end; i++) {
            int size = sums.size();
            for (int j = 0; j < size; j++) {
                sums.add(sums.get(j) + nums[i]);
            }
        }
        return sums;
    }

    public static void main(String[] args) {
        System.out.println(minAbsDifference(new int[]{5,-7,3,5}, 6));        // 0
        System.out.println(minAbsDifference(new int[]{7,-9,15,-2}, -5));     // 1
        System.out.println(minAbsDifference(new int[]{1,2,3}, 100));         // 94
        System.out.println(minAbsDifference(new int[]{1,2,3}, -7));          // 7
    }
}

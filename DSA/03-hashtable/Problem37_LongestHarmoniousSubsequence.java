import java.util.*;

/**
 * Problem 37: Longest Harmonious Subsequence
 * Find longest subsequence where max - min = 1.
 *
 * Approach: Count frequencies. For each key k, check if k+1 exists; sum their counts.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like finding the largest group of users whose activity levels
 * differ by at most 1 tier for cohort analysis.
 */
public class Problem37_LongestHarmoniousSubsequence {
    public int findLHS(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        for (int n : nums) freq.merge(n, 1, Integer::sum);
        int max = 0;
        for (int key : freq.keySet()) {
            if (freq.containsKey(key + 1)) {
                max = Math.max(max, freq.get(key) + freq.get(key + 1));
            }
        }
        return max;
    }

    public static void main(String[] args) {
        Problem37_LongestHarmoniousSubsequence sol = new Problem37_LongestHarmoniousSubsequence();
        System.out.println(sol.findLHS(new int[]{1,3,2,2,5,2,3,7})); // 5
        System.out.println(sol.findLHS(new int[]{1,2,3,4})); // 2
        System.out.println(sol.findLHS(new int[]{1,1,1,1})); // 0
    }
}

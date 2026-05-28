import java.util.*;

/**
 * Problem 10: Longest Consecutive Sequence
 * Given an unsorted array, find the length of the longest consecutive elements sequence in O(n).
 *
 * Approach: Put all numbers in a HashSet. For each number that is the START of a sequence
 * (num-1 not in set), count consecutive numbers forward.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like finding the longest uninterrupted uptime window in a monitoring system.
 * Each timestamp is checked to see if it starts a continuous sequence.
 */
public class Problem10_LongestConsecutiveSequence {
    public int longestConsecutive(int[] nums) {
        Set<Integer> set = new HashSet<>();
        for (int n : nums) set.add(n);
        int maxLen = 0;
        for (int n : set) {
            if (!set.contains(n - 1)) { // start of sequence
                int len = 1;
                while (set.contains(n + len)) len++;
                maxLen = Math.max(maxLen, len);
            }
        }
        return maxLen;
    }

    public static void main(String[] args) {
        Problem10_LongestConsecutiveSequence sol = new Problem10_LongestConsecutiveSequence();
        System.out.println(sol.longestConsecutive(new int[]{100,4,200,1,3,2})); // 4
        System.out.println(sol.longestConsecutive(new int[]{0,3,7,2,5,8,4,6,0,1})); // 9
        System.out.println(sol.longestConsecutive(new int[]{})); // 0
        System.out.println(sol.longestConsecutive(new int[]{1,2,0,1})); // 3
    }
}

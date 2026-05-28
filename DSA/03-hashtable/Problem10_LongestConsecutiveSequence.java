import java.util.*;

/**
 * Problem 10: Longest Consecutive Sequence
 * Find the length of the longest consecutive elements sequence in O(n).
 *
 * Approach: Put all numbers in HashSet. For each number that is a sequence start
 * (num-1 not in set), count consecutive elements.
 *
 * Time Complexity: O(n) - each element visited at most twice
 * Space Complexity: O(n)
 *
 * Production Analogy: Gap detection in event streams - finding longest uninterrupted
 * sequence of sequential IDs (detecting missing messages in distributed queues).
 */
public class Problem10_LongestConsecutiveSequence {
    public int longestConsecutive(int[] nums) {
        Set<Integer> set = new HashSet<>();
        for (int n : nums) set.add(n);
        int longest = 0;
        for (int num : set) {
            if (!set.contains(num - 1)) { // start of sequence
                int len = 1;
                while (set.contains(num + len)) len++;
                longest = Math.max(longest, len);
            }
        }
        return longest;
    }

    public static void main(String[] args) {
        Problem10_LongestConsecutiveSequence sol = new Problem10_LongestConsecutiveSequence();
        System.out.println(sol.longestConsecutive(new int[]{100,4,200,1,3,2})); // 4
        System.out.println(sol.longestConsecutive(new int[]{0,3,7,2,5,8,4,6,0,1})); // 9
        System.out.println(sol.longestConsecutive(new int[]{})); // 0
        System.out.println(sol.longestConsecutive(new int[]{1,2,0,1})); // 3
    }
}

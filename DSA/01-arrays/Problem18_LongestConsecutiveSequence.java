import java.util.*;

/**
 * Problem 18: Longest Consecutive Sequence
 * Find length of longest consecutive elements sequence in O(n).
 * 
 * Production Analogy: Like detecting the longest uninterrupted session streak -
 * use a HashSet to efficiently check sequence continuity.
 * 
 * O(n) time, O(n) space - HashSet, only start counting from sequence starts
 */
public class Problem18_LongestConsecutiveSequence {

    public static int longestConsecutive(int[] nums) {
        Set<Integer> set = new HashSet<>();
        for (int n : nums) set.add(n);
        int longest = 0;
        for (int n : set) {
            if (!set.contains(n - 1)) { // start of sequence
                int len = 1;
                while (set.contains(n + len)) len++;
                longest = Math.max(longest, len);
            }
        }
        return longest;
    }

    public static void main(String[] args) {
        System.out.println(longestConsecutive(new int[]{100,4,200,1,3,2})); // 4
        System.out.println(longestConsecutive(new int[]{0,3,7,2,5,8,4,6,0,1})); // 9
        System.out.println(longestConsecutive(new int[]{})); // 0
    }
}

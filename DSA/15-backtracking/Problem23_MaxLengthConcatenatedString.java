import java.util.*;

/**
 * Problem 23: Maximum Length of a Concatenated String with Unique Characters (LeetCode 1239)
 * 
 * Find max length of concatenation of a subsequence of arr where all chars are unique.
 * 
 * Search Tree:
 * - For each string, include or exclude it (subset-style)
 * - Track used characters with bitmask or set
 * 
 * Pruning Strategy:
 * - Skip strings that have duplicate characters internally
 * - Skip if string conflicts with current character set
 * 
 * Time Complexity: O(2^n * 26)
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Maximizing unique feature coverage: selecting maximum non-overlapping service capabilities.
 */
public class Problem23_MaxLengthConcatenatedString {

    private int maxLen;

    public int maxLength(List<String> arr) {
        maxLen = 0;
        backtrack(arr, 0, 0);
        return maxLen;
    }

    private void backtrack(List<String> arr, int idx, int used) {
        maxLen = Math.max(maxLen, Integer.bitCount(used));
        for (int i = idx; i < arr.size(); i++) {
            int mask = getMask(arr.get(i));
            if (mask == -1) continue; // string has internal duplicates
            if ((used & mask) != 0) continue; // conflict with current
            backtrack(arr, i + 1, used | mask);
        }
    }

    private int getMask(String s) {
        int mask = 0;
        for (char c : s.toCharArray()) {
            int bit = 1 << (c - 'a');
            if ((mask & bit) != 0) return -1;
            mask |= bit;
        }
        return mask;
    }

    public static void main(String[] args) {
        Problem23_MaxLengthConcatenatedString sol = new Problem23_MaxLengthConcatenatedString();

        System.out.println(sol.maxLength(Arrays.asList("un","iq","ue"))); // 4
        System.out.println(sol.maxLength(Arrays.asList("cha","r","act","ers"))); // 6
        System.out.println(sol.maxLength(Arrays.asList("abcdefghijklmnopqrstuvwxyz"))); // 26
    }
}

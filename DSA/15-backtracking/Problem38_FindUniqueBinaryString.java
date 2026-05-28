import java.util.*;

/**
 * Problem 38: Find Unique Binary String (LeetCode 1980)
 * 
 * Given n unique binary strings of length n, find a binary string of length n not in the list.
 * 
 * Search Tree:
 * - Build string char by char (0 or 1), check if complete string is NOT in set
 * - Alternatively, use Cantor's diagonal argument (flip bit i of string i)
 * 
 * Pruning Strategy:
 * - Diagonal approach needs no backtracking (O(n) solution)
 * - Backtracking approach: if prefix already matches no string in set, we can stop early
 * 
 * Time Complexity: O(n) with diagonal trick, O(2^n) worst case with backtracking
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Generating unique identifiers guaranteed to not conflict with existing entries.
 */
public class Problem38_FindUniqueBinaryString {

    // Elegant O(n) solution using Cantor's diagonal argument
    public String findDifferentBinaryString(String[] nums) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < nums.length; i++) {
            // Flip bit i of string i -> guaranteed to differ from every string
            sb.append(nums[i].charAt(i) == '0' ? '1' : '0');
        }
        return sb.toString();
    }

    // Backtracking approach for learning purposes
    public String findDifferentBinaryStringBT(String[] nums) {
        Set<String> set = new HashSet<>(Arrays.asList(nums));
        int n = nums.length;
        return backtrack(set, n, new StringBuilder());
    }

    private String backtrack(Set<String> set, int n, StringBuilder sb) {
        if (sb.length() == n) {
            String s = sb.toString();
            return set.contains(s) ? null : s;
        }
        for (char c : new char[]{'0', '1'}) {
            sb.append(c);
            String result = backtrack(set, n, sb);
            if (result != null) return result;
            sb.deleteCharAt(sb.length() - 1);
        }
        return null;
    }

    public static void main(String[] args) {
        Problem38_FindUniqueBinaryString sol = new Problem38_FindUniqueBinaryString();

        System.out.println(sol.findDifferentBinaryString(new String[]{"01","10"}));
        System.out.println(sol.findDifferentBinaryString(new String[]{"00","01"}));
        System.out.println(sol.findDifferentBinaryString(new String[]{"111","011","001"}));

        System.out.println(sol.findDifferentBinaryStringBT(new String[]{"01","10"}));
    }
}

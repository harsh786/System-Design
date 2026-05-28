import java.util.*;

/**
 * Problem 15: Palindrome Partitioning (LeetCode 131)
 * 
 * Partition string s such that every substring is a palindrome. Return all partitions.
 * 
 * Search Tree:
 * - At index i, try all substrings s[i..j] where j in [i, n-1]
 * - If s[i..j] is palindrome, recurse from j+1
 * 
 * Pruning Strategy:
 * - Only recurse if current substring IS a palindrome (skip non-palindromes immediately)
 * - Can precompute palindrome table with DP for O(1) checks
 * 
 * Time Complexity: O(n * 2^n) 
 * Space Complexity: O(n) recursion depth
 * 
 * Production Analogy:
 * - Log segmentation: splitting a log stream into valid, self-contained chunks for parallel processing.
 */
public class Problem15_PalindromePartitioning {

    public List<List<String>> partition(String s) {
        List<List<String>> result = new ArrayList<>();
        backtrack(s, 0, new ArrayList<>(), result);
        return result;
    }

    private void backtrack(String s, int start, List<String> current, List<List<String>> result) {
        if (start == s.length()) {
            result.add(new ArrayList<>(current));
            return;
        }
        for (int end = start; end < s.length(); end++) {
            if (isPalindrome(s, start, end)) {
                current.add(s.substring(start, end + 1));
                backtrack(s, end + 1, current, result);
                current.remove(current.size() - 1);
            }
        }
    }

    private boolean isPalindrome(String s, int l, int r) {
        while (l < r) { if (s.charAt(l++) != s.charAt(r--)) return false; }
        return true;
    }

    public static void main(String[] args) {
        Problem15_PalindromePartitioning sol = new Problem15_PalindromePartitioning();

        System.out.println(sol.partition("aab"));  // [[a,a,b],[aa,b]]
        System.out.println(sol.partition("a"));    // [[a]]
        System.out.println(sol.partition("abba")); 
    }
}

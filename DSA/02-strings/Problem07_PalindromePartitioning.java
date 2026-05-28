import java.util.*;

/**
 * Problem 7: Palindrome Partitioning (LeetCode 131)
 * 
 * Partition s such that every substring is a palindrome. Return all possible partitions.
 * 
 * Approach: Backtracking. For each position, try all palindrome prefixes and recurse.
 * O(n * 2^n) time, O(n) space for recursion.
 * 
 * Production Analogy: Like splitting a monolith into microservices where each service
 * must be "self-contained" (palindromic = self-sufficient).
 */
public class Problem07_PalindromePartitioning {

    public static List<List<String>> partition(String s) {
        List<List<String>> result = new ArrayList<>();
        backtrack(s, 0, new ArrayList<>(), result);
        return result;
    }

    private static void backtrack(String s, int start, List<String> path, List<List<String>> result) {
        if (start == s.length()) {
            result.add(new ArrayList<>(path));
            return;
        }
        for (int end = start; end < s.length(); end++) {
            if (isPalin(s, start, end)) {
                path.add(s.substring(start, end + 1));
                backtrack(s, end + 1, path, result);
                path.remove(path.size() - 1);
            }
        }
    }

    private static boolean isPalin(String s, int l, int r) {
        while (l < r) { if (s.charAt(l++) != s.charAt(r--)) return false; }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(partition("aab"));  // [[a,a,b],[aa,b]]
        System.out.println(partition("a"));    // [[a]]
        System.out.println(partition("abc"));  // [[a,b,c]]
    }
}

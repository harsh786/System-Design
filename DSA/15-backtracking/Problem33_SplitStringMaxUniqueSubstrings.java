import java.util.*;

/**
 * Problem 33: Split a String Into Max Number of Unique Substrings (LeetCode 1593)
 * 
 * Split string s into maximum number of non-empty unique substrings.
 * 
 * Search Tree:
 * - At index i, try all substrings s[i..j] for j in [i, n-1]
 * - If substring not already used, add to set and recurse from j+1
 * 
 * Pruning Strategy:
 * - If remaining length + current count can't beat best, prune
 * - Skip substrings already in the used set
 * 
 * Time Complexity: O(2^n * n) in worst case
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Log tokenization: maximizing unique tokens for better indexing/searchability.
 */
public class Problem33_SplitStringMaxUniqueSubstrings {

    private int maxCount;

    public int maxUniqueSplit(String s) {
        maxCount = 0;
        backtrack(s, 0, new HashSet<>());
        return maxCount;
    }

    private void backtrack(String s, int start, Set<String> seen) {
        if (start == s.length()) {
            maxCount = Math.max(maxCount, seen.size());
            return;
        }
        // Pruning: even if every remaining char is unique substring, can we beat current max?
        if (seen.size() + (s.length() - start) <= maxCount) return;

        for (int end = start + 1; end <= s.length(); end++) {
            String sub = s.substring(start, end);
            if (seen.contains(sub)) continue;
            seen.add(sub);
            backtrack(s, end, seen);
            seen.remove(sub);
        }
    }

    public static void main(String[] args) {
        Problem33_SplitStringMaxUniqueSubstrings sol = new Problem33_SplitStringMaxUniqueSubstrings();

        System.out.println(sol.maxUniqueSplit("ababccc")); // 5
        System.out.println(sol.maxUniqueSplit("aba"));     // 2
        System.out.println(sol.maxUniqueSplit("aa"));      // 1
    }
}

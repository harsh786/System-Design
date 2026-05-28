import java.util.*;

/**
 * Problem 21: Remove Invalid Parentheses (LeetCode 301)
 * 
 * Remove minimum number of invalid parentheses to make the string valid.
 * 
 * Search Tree:
 * - First compute min removals needed (count mismatched open/close)
 * - BFS or DFS: try removing each '(' or ')' and check validity
 * 
 * Pruning Strategy:
 * - Calculate exact number of '(' and ')' to remove
 * - Only remove characters that are parentheses
 * - Skip consecutive same characters to avoid duplicates
 * - Use index tracking to only remove from current position forward
 * 
 * Time Complexity: O(2^n) worst case
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Minimal error correction in structured data streams (fixing malformed XML/JSON).
 */
public class Problem21_RemoveInvalidParentheses {

    public List<String> removeInvalidParentheses(String s) {
        List<String> result = new ArrayList<>();
        int rmL = 0, rmR = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') rmL++;
            else if (c == ')') {
                if (rmL > 0) rmL--;
                else rmR++;
            }
        }
        dfs(s, 0, rmL, rmR, result);
        return result;
    }

    private void dfs(String s, int start, int rmL, int rmR, List<String> result) {
        if (rmL == 0 && rmR == 0) {
            if (isValid(s)) result.add(s);
            return;
        }
        for (int i = start; i < s.length(); i++) {
            if (i > start && s.charAt(i) == s.charAt(i - 1)) continue; // skip dups
            if (s.charAt(i) == '(' && rmL > 0) {
                dfs(s.substring(0, i) + s.substring(i + 1), i, rmL - 1, rmR, result);
            } else if (s.charAt(i) == ')' && rmR > 0) {
                dfs(s.substring(0, i) + s.substring(i + 1), i, rmL, rmR - 1, result);
            }
        }
    }

    private boolean isValid(String s) {
        int count = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') count++;
            else if (c == ')') count--;
            if (count < 0) return false;
        }
        return count == 0;
    }

    public static void main(String[] args) {
        Problem21_RemoveInvalidParentheses sol = new Problem21_RemoveInvalidParentheses();

        System.out.println(sol.removeInvalidParentheses("()())()")); // ["(())()","()()()"]
        System.out.println(sol.removeInvalidParentheses("(a)())()"));
        System.out.println(sol.removeInvalidParentheses(")(")); // [""]
    }
}

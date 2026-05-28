import java.util.*;

/**
 * Problem 22: Generate Parentheses (LeetCode 22)
 * 
 * Approach: Backtracking. Add '(' if open < n, add ')' if close < open.
 * O(4^n / sqrt(n)) time (Catalan number), O(n) space.
 * 
 * Production Analogy: Like generating all valid state machine transition sequences.
 */
public class Problem22_GenerateParentheses {

    public static List<String> generateParenthesis(int n) {
        List<String> result = new ArrayList<>();
        backtrack(result, new StringBuilder(), 0, 0, n);
        return result;
    }

    private static void backtrack(List<String> result, StringBuilder sb, int open, int close, int n) {
        if (sb.length() == 2 * n) { result.add(sb.toString()); return; }
        if (open < n) { sb.append('('); backtrack(result, sb, open + 1, close, n); sb.deleteCharAt(sb.length() - 1); }
        if (close < open) { sb.append(')'); backtrack(result, sb, open, close + 1, n); sb.deleteCharAt(sb.length() - 1); }
    }

    public static void main(String[] args) {
        System.out.println(generateParenthesis(3)); // ["((()))","(()())","(())()","()(())","()()()"]
        System.out.println(generateParenthesis(1)); // ["()"]
    }
}

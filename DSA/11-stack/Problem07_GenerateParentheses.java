import java.util.*;

/**
 * Problem 7: Generate Parentheses (LeetCode 22)
 * 
 * Generate all combinations of well-formed parentheses given n pairs.
 * 
 * Approach: Backtracking with implicit stack (recursion). Add '(' if open < n,
 * add ')' if close < open. Base case when length == 2*n.
 * 
 * Time Complexity: O(4^n / sqrt(n)) - Catalan number
 * Space Complexity: O(n) recursion depth
 * 
 * Production Analogy: Like generating all valid configuration combinations
 * for nested resource hierarchies (VPCs > Subnets > Security Groups).
 */
public class Problem07_GenerateParentheses {

    public static List<String> generateParenthesis(int n) {
        List<String> result = new ArrayList<>();
        backtrack(result, new StringBuilder(), 0, 0, n);
        return result;
    }

    private static void backtrack(List<String> result, StringBuilder sb, int open, int close, int n) {
        if (sb.length() == 2 * n) {
            result.add(sb.toString());
            return;
        }
        if (open < n) {
            sb.append('(');
            backtrack(result, sb, open + 1, close, n);
            sb.deleteCharAt(sb.length() - 1);
        }
        if (close < open) {
            sb.append(')');
            backtrack(result, sb, open, close + 1, n);
            sb.deleteCharAt(sb.length() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(generateParenthesis(3)); // [((())), (()()), (())(), ()(()), ()()()]
        System.out.println(generateParenthesis(1)); // [()]
        System.out.println(generateParenthesis(0)); // []  - empty string
    }
}

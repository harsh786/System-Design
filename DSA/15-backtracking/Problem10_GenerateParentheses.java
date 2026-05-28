import java.util.*;

/**
 * Problem 10: Generate Parentheses (LeetCode 22)
 * 
 * Generate all combinations of well-formed parentheses for n pairs.
 * 
 * Search Tree:
 * - At each position, choose '(' or ')'
 * - Constraints: open < n to add '(', close < open to add ')'
 * 
 * Pruning Strategy:
 * - Only add '(' if open count < n
 * - Only add ')' if close count < open count
 * - This ensures only valid parentheses are generated (no invalid paths explored)
 * 
 * Time Complexity: O(4^n / sqrt(n)) - nth Catalan number
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Generating valid nested transaction scopes or valid XML/JSON bracket structures.
 */
public class Problem10_GenerateParentheses {

    public List<String> generateParenthesis(int n) {
        List<String> result = new ArrayList<>();
        backtrack(n, 0, 0, new StringBuilder(), result);
        return result;
    }

    private void backtrack(int n, int open, int close, StringBuilder current, List<String> result) {
        if (current.length() == 2 * n) {
            result.add(current.toString());
            return;
        }
        if (open < n) {
            current.append('(');
            backtrack(n, open + 1, close, current, result);
            current.deleteCharAt(current.length() - 1);
        }
        if (close < open) {
            current.append(')');
            backtrack(n, open, close + 1, current, result);
            current.deleteCharAt(current.length() - 1);
        }
    }

    public static void main(String[] args) {
        Problem10_GenerateParentheses sol = new Problem10_GenerateParentheses();

        System.out.println(sol.generateParenthesis(3));
        System.out.println(sol.generateParenthesis(1)); // [()]
        System.out.println(sol.generateParenthesis(0)); // []... actually [""]
        System.out.println(sol.generateParenthesis(4));
    }
}

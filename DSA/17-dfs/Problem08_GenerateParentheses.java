import java.util.*;

/**
 * Problem: Generate Parentheses (LeetCode 22)
 * Approach: DFS/backtracking - track open/close count, only add valid choices
 * Time: O(4^n/sqrt(n)) Catalan number, Space: O(n)
 * Production Analogy: Generating valid configuration templates with nested scopes
 */
public class Problem08_GenerateParentheses {
    public List<String> generateParenthesis(int n) {
        List<String> res = new ArrayList<>();
        dfs(res, new StringBuilder(), 0, 0, n);
        return res;
    }

    private void dfs(List<String> res, StringBuilder sb, int open, int close, int n) {
        if (sb.length() == 2 * n) { res.add(sb.toString()); return; }
        if (open < n) { sb.append('('); dfs(res, sb, open+1, close, n); sb.deleteCharAt(sb.length()-1); }
        if (close < open) { sb.append(')'); dfs(res, sb, open, close+1, n); sb.deleteCharAt(sb.length()-1); }
    }

    public static void main(String[] args) {
        System.out.println(new Problem08_GenerateParentheses().generateParenthesis(3));
    }
}

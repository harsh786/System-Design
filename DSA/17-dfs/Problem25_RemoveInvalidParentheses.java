import java.util.*;

/**
 * Problem: Remove Invalid Parentheses (LeetCode 301)
 * Approach: DFS - count min removals needed, then backtrack trying all removal combos
 * Time: O(2^N), Space: O(N)
 * Production Analogy: Auto-correcting malformed API request payloads with minimal edits
 */
public class Problem25_RemoveInvalidParentheses {
    public List<String> removeInvalidParentheses(String s) {
        int openRem = 0, closeRem = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') openRem++;
            else if (c == ')') { if (openRem > 0) openRem--; else closeRem++; }
        }
        Set<String> res = new HashSet<>();
        dfs(s, 0, 0, 0, openRem, closeRem, new StringBuilder(), res);
        return new ArrayList<>(res);
    }

    private void dfs(String s, int i, int open, int close, int openRem, int closeRem, StringBuilder sb, Set<String> res) {
        if (i == s.length()) { if (openRem == 0 && closeRem == 0) res.add(sb.toString()); return; }
        char c = s.charAt(i);
        int len = sb.length();
        if (c == '(' && openRem > 0) dfs(s, i+1, open, close, openRem-1, closeRem, sb, res);
        if (c == ')' && closeRem > 0) dfs(s, i+1, open, close, openRem, closeRem-1, sb, res);
        sb.append(c);
        if (c != '(' && c != ')') dfs(s, i+1, open, close, openRem, closeRem, sb, res);
        else if (c == '(') dfs(s, i+1, open+1, close, openRem, closeRem, sb, res);
        else if (close < open) dfs(s, i+1, open, close+1, openRem, closeRem, sb, res);
        sb.setLength(len);
    }

    public static void main(String[] args) {
        System.out.println(new Problem25_RemoveInvalidParentheses().removeInvalidParentheses("()())()"));
    }
}

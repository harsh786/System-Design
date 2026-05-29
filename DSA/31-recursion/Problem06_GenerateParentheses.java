import java.util.*;

public class Problem06_GenerateParentheses {
    public static List<String> generateParenthesis(int n) {
        List<String> res = new ArrayList<>();
        generate(res, new StringBuilder(), 0, 0, n);
        return res;
    }
    static void generate(List<String> res, StringBuilder sb, int open, int close, int n) {
        if (sb.length() == 2 * n) { res.add(sb.toString()); return; }
        if (open < n) { sb.append('('); generate(res, sb, open + 1, close, n); sb.deleteCharAt(sb.length() - 1); }
        if (close < open) { sb.append(')'); generate(res, sb, open, close + 1, n); sb.deleteCharAt(sb.length() - 1); }
    }
    public static void main(String[] args) {
        System.out.println(generateParenthesis(3));
    }
}

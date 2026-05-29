import java.util.*;

public class Problem38_ExpressionAddOperators {
    public static List<String> addOperators(String num, int target) {
        List<String> res = new ArrayList<>();
        dfs(res, num, target, 0, 0, 0, "");
        return res;
    }
    static void dfs(List<String> res, String num, int target, int idx, long eval, long multed, String path) {
        if (idx == num.length()) { if (eval == target) res.add(path); return; }
        for (int i = idx; i < num.length(); i++) {
            if (i != idx && num.charAt(idx) == '0') break;
            long cur = Long.parseLong(num.substring(idx, i + 1));
            if (idx == 0) { dfs(res, num, target, i + 1, cur, cur, "" + cur); }
            else {
                dfs(res, num, target, i + 1, eval + cur, cur, path + "+" + cur);
                dfs(res, num, target, i + 1, eval - cur, -cur, path + "-" + cur);
                dfs(res, num, target, i + 1, eval - multed + multed * cur, multed * cur, path + "*" + cur);
            }
        }
    }
    public static void main(String[] args) {
        System.out.println(addOperators("123", 6)); // [1+2+3, 1*2*3]
    }
}

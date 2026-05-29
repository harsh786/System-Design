import java.util.*;

public class Problem37_RestoreIPAddresses {
    public static List<String> restoreIpAddresses(String s) {
        List<String> res = new ArrayList<>();
        backtrack(res, new ArrayList<>(), s, 0);
        return res;
    }
    static void backtrack(List<String> res, List<String> cur, String s, int start) {
        if (cur.size() == 4 && start == s.length()) { res.add(String.join(".", cur)); return; }
        if (cur.size() == 4 || start == s.length()) return;
        for (int len = 1; len <= 3 && start + len <= s.length(); len++) {
            String part = s.substring(start, start + len);
            if ((part.length() > 1 && part.startsWith("0")) || Integer.parseInt(part) > 255) continue;
            cur.add(part); backtrack(res, cur, s, start + len); cur.remove(cur.size() - 1);
        }
    }
    public static void main(String[] args) {
        System.out.println(restoreIpAddresses("25525511135"));
    }
}

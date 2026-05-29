import java.util.*;

public class Problem36_PalindromePartitioning {
    public static List<List<String>> partition(String s) {
        List<List<String>> res = new ArrayList<>();
        backtrack(res, new ArrayList<>(), s, 0);
        return res;
    }
    static void backtrack(List<List<String>> res, List<String> cur, String s, int start) {
        if (start == s.length()) { res.add(new ArrayList<>(cur)); return; }
        for (int end = start; end < s.length(); end++) {
            if (isPalindrome(s, start, end)) {
                cur.add(s.substring(start, end + 1));
                backtrack(res, cur, s, end + 1);
                cur.remove(cur.size() - 1);
            }
        }
    }
    static boolean isPalindrome(String s, int l, int r) { while (l < r) if (s.charAt(l++) != s.charAt(r--)) return false; return true; }
    public static void main(String[] args) {
        System.out.println(partition("aab"));
    }
}

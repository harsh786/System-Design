import java.util.*;

public class Problem05_LongestDuplicateSubstring {
    private static final long MOD = (1L << 61) - 1;
    private static final long BASE = 31;

    public String longestDupSubstring(String s) {
        int lo = 1, hi = s.length() - 1;
        String result = "";
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            String dup = check(s, mid);
            if (dup != null) { result = dup; lo = mid + 1; }
            else hi = mid - 1;
        }
        return result;
    }

    private String check(String s, int len) {
        long hash = 0, power = 1;
        for (int i = 0; i < len; i++) { hash = (hash * BASE + s.charAt(i)) % MOD; if (i > 0) power = power * BASE % MOD; }
        Map<Long, List<Integer>> seen = new HashMap<>();
        seen.computeIfAbsent(hash, k -> new ArrayList<>()).add(0);
        for (int i = 1; i + len <= s.length(); i++) {
            hash = ((hash - s.charAt(i-1) * power % MOD + MOD) * BASE + s.charAt(i+len-1)) % MOD;
            List<Integer> list = seen.get(hash);
            if (list != null) {
                String cur = s.substring(i, i + len);
                for (int j : list) if (s.substring(j, j + len).equals(cur)) return cur;
            }
            seen.computeIfAbsent(hash, k -> new ArrayList<>()).add(i);
        }
        return null;
    }

    public static void main(String[] args) {
        Problem05_LongestDuplicateSubstring sol = new Problem05_LongestDuplicateSubstring();
        System.out.println(sol.longestDupSubstring("banana")); // "ana"
    }
}

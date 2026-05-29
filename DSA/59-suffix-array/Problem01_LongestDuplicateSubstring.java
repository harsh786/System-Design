import java.util.*;

public class Problem01_LongestDuplicateSubstring {
    // Binary search on length + Rabin-Karp rolling hash
    public static String longestDupSubstring(String s) {
        int lo = 1, hi = s.length() - 1;
        String result = "";
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            String dup = findDuplicate(s, mid);
            if (dup != null) { result = dup; lo = mid + 1; }
            else hi = mid - 1;
        }
        return result;
    }

    static String findDuplicate(String s, int len) {
        long MOD = (1L << 61) - 1, base = 31;
        long hash = 0, power = 1;
        for (int i = 0; i < len; i++) { hash = (hash * base + s.charAt(i)) % MOD; if (i>0) power = power * base % MOD; }
        Map<Long, List<Integer>> seen = new HashMap<>();
        seen.computeIfAbsent(hash, k -> new ArrayList<>()).add(0);
        for (int i = 1; i + len <= s.length(); i++) {
            hash = (hash - s.charAt(i-1) * power % MOD + MOD) % MOD;
            hash = (hash * base + s.charAt(i + len - 1)) % MOD;
            List<Integer> list = seen.get(hash);
            if (list != null) {
                String cur = s.substring(i, i + len);
                for (int prev : list) if (s.substring(prev, prev+len).equals(cur)) return cur;
            }
            seen.computeIfAbsent(hash, k -> new ArrayList<>()).add(i);
        }
        return null;
    }

    public static void main(String[] args) {
        System.out.println(longestDupSubstring("banana")); // ana
        System.out.println(longestDupSubstring("abcd")); // ""
    }
}

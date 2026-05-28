import java.util.*;

/**
 * Problem 47: Longest Duplicate Substring (LeetCode 1044)
 * 
 * Approach: Binary search on length + Rabin-Karp rolling hash. O(n log n) time avg.
 * 
 * Production Analogy: Like deduplication in storage systems - finding the longest
 * repeated block to maximize compression.
 */
public class Problem47_LongestDuplicateSubstring {

    public static String longestDupSubstring(String s) {
        int lo = 1, hi = s.length() - 1;
        String result = "";
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            String dup = findDup(s, mid);
            if (dup != null) {
                result = dup;
                lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }
        return result;
    }

    private static String findDup(String s, int len) {
        long MOD = (1L << 61) - 1, BASE = 31;
        long hash = 0, pow = 1;
        for (int i = 0; i < len; i++) {
            hash = (hash * BASE + s.charAt(i)) % MOD;
            if (i > 0) pow = pow * BASE % MOD;
        }
        Map<Long, List<Integer>> seen = new HashMap<>();
        seen.computeIfAbsent(hash, k -> new ArrayList<>()).add(0);
        for (int i = 1; i <= s.length() - len; i++) {
            hash = (hash - s.charAt(i - 1) * pow % MOD + MOD) % MOD;
            hash = (hash * BASE + s.charAt(i + len - 1)) % MOD;
            List<Integer> indices = seen.get(hash);
            if (indices != null) {
                String candidate = s.substring(i, i + len);
                for (int idx : indices) {
                    if (s.substring(idx, idx + len).equals(candidate)) return candidate;
                }
            }
            seen.computeIfAbsent(hash, k -> new ArrayList<>()).add(i);
        }
        return null;
    }

    public static void main(String[] args) {
        System.out.println(longestDupSubstring("banana")); // "ana"
        System.out.println(longestDupSubstring("abcd"));   // ""
        System.out.println(longestDupSubstring("aa"));     // "a"
    }
}

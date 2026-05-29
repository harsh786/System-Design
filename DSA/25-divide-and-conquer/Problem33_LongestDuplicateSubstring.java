import java.util.*;

/**
 * Problem 33: Longest Duplicate Substring (LeetCode 1044)
 * 
 * D&C Approach (Binary Search + Rolling Hash):
 * - DIVIDE: Binary search on the length of duplicate substring
 * - CONQUER: For a given length, use Rabin-Karp rolling hash to check if
 *   any duplicate substring of that length exists
 * - Monotonicity: if duplicate of length L exists, duplicate of length L-1 also exists
 * 
 * Time: O(n log n) average with rolling hash, O(n^2 log n) worst
 * Space: O(n)
 * 
 * Production Analogy:
 * - Deduplication in storage systems (finding repeated blocks)
 * - Plagiarism detection (longest common passages)
 * - DNA sequence analysis (finding repeated motifs)
 */
public class Problem33_LongestDuplicateSubstring {

    public static String longestDupSubstring(String s) {
        int lo = 1, hi = s.length() - 1;
        String result = "";
        
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            String dup = findDuplicate(s, mid);
            if (dup != null) {
                result = dup;
                lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }
        return result;
    }

    private static String findDuplicate(String s, int len) {
        long MOD = (1L << 31) - 1;
        long BASE = 26;
        long hash = 0;
        long pow = 1;
        
        for (int i = 0; i < len; i++) {
            hash = (hash * BASE + (s.charAt(i) - 'a')) % MOD;
            if (i > 0) pow = (pow * BASE) % MOD;
        }
        
        Map<Long, List<Integer>> seen = new HashMap<>();
        seen.computeIfAbsent(hash, k -> new ArrayList<>()).add(0);
        
        for (int i = 1; i + len - 1 < s.length(); i++) {
            hash = (hash - (s.charAt(i - 1) - 'a') * pow % MOD + MOD) % MOD;
            hash = (hash * BASE + (s.charAt(i + len - 1) - 'a')) % MOD;
            
            List<Integer> positions = seen.get(hash);
            if (positions != null) {
                String candidate = s.substring(i, i + len);
                for (int pos : positions) {
                    if (s.substring(pos, pos + len).equals(candidate)) return candidate;
                }
            }
            seen.computeIfAbsent(hash, k -> new ArrayList<>()).add(i);
        }
        return null;
    }

    public static void main(String[] args) {
        System.out.println(longestDupSubstring("banana"));       // "ana"
        System.out.println(longestDupSubstring("abcd"));         // ""
        System.out.println(longestDupSubstring("aa"));           // "a"
        System.out.println(longestDupSubstring("aabaabaab"));    // "aabaa" or similar
    }
}

import java.util.*;

/**
 * Problem 46: Longest Duplicate Substring (Trie approach)
 * 
 * Find the longest substring that appears at least twice.
 * Binary search on length + trie/rolling hash to check existence.
 * Note: Pure trie approach is O(n^2) space; binary search + hash is better for large inputs.
 * 
 * Time Complexity: O(n^2) with trie, O(n*log(n)) with binary search + rolling hash
 * Space Complexity: O(n^2) with trie
 * 
 * Production Analogy: Data deduplication in storage systems, finding repeated code blocks
 * (copy-paste detection), music plagiarism detection, genome repeat analysis.
 */
public class Problem46_LongestDuplicateSubstring {

    static class TrieNode {
        TrieNode[] children = new TrieNode[26];
    }

    // Trie approach: insert all suffixes, find deepest node visited twice
    public static String longestDupSubstring(String s) {
        // Binary search on length for efficiency
        int lo = 1, hi = s.length() - 1;
        String result = "";
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
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

    // Check if there's a duplicate substring of given length using rolling hash
    static String findDuplicate(String s, int len) {
        long MOD = (1L << 61) - 1;
        long BASE = 31;
        long hash = 0, power = 1;
        Set<Long> seen = new HashSet<>();

        for (int i = 0; i < len; i++) {
            hash = (hash * BASE + (s.charAt(i) - 'a' + 1)) % MOD;
            if (i < len - 1) power = (power * BASE) % MOD;
        }
        seen.add(hash);
        for (int i = len; i < s.length(); i++) {
            hash = (hash - (s.charAt(i - len) - 'a' + 1) * power % MOD + MOD) % MOD;
            hash = (hash * BASE + (s.charAt(i) - 'a' + 1)) % MOD;
            if (!seen.add(hash)) return s.substring(i - len + 1, i + 1);
        }
        return null;
    }

    public static void main(String[] args) {
        System.out.println(longestDupSubstring("banana"));  // "ana"
        System.out.println(longestDupSubstring("abcd"));    // ""
        System.out.println(longestDupSubstring("aabaa"));   // "aa"
        System.out.println(longestDupSubstring("aaaa"));    // "aaa"
    }
}

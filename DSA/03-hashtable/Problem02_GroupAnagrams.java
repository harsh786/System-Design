import java.util.*;

/**
 * Problem 2: Group Anagrams
 * Given an array of strings, group anagrams together.
 *
 * Approach: Sort each string to create a canonical key, group by that key in a HashMap.
 * Alternative: Use character frequency array as key for O(n*k) instead of O(n*k*log(k)).
 *
 * Time Complexity: O(n * k * log(k)) where k is max string length
 * Space Complexity: O(n * k)
 *
 * Production Analogy: Like content deduplication in a distributed storage system.
 * Files with same content but different names are grouped by content hash.
 */
public class Problem02_GroupAnagrams {
    public List<List<String>> groupAnagrams(String[] strs) {
        Map<String, List<String>> map = new HashMap<>();
        for (String s : strs) {
            char[] chars = s.toCharArray();
            Arrays.sort(chars);
            String key = new String(chars);
            map.computeIfAbsent(key, k -> new ArrayList<>()).add(s);
        }
        return new ArrayList<>(map.values());
    }

    // Optimal: frequency-based key
    public List<List<String>> groupAnagramsOptimal(String[] strs) {
        Map<String, List<String>> map = new HashMap<>();
        for (String s : strs) {
            int[] count = new int[26];
            for (char c : s.toCharArray()) count[c - 'a']++;
            String key = Arrays.toString(count);
            map.computeIfAbsent(key, k -> new ArrayList<>()).add(s);
        }
        return new ArrayList<>(map.values());
    }

    public static void main(String[] args) {
        Problem02_GroupAnagrams sol = new Problem02_GroupAnagrams();
        System.out.println(sol.groupAnagrams(new String[]{"eat","tea","tan","ate","nat","bat"}));
        System.out.println(sol.groupAnagrams(new String[]{""}));
        System.out.println(sol.groupAnagrams(new String[]{"a"}));
        System.out.println(sol.groupAnagramsOptimal(new String[]{"eat","tea","tan","ate","nat","bat"}));
    }
}

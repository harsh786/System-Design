import java.util.*;

/**
 * Problem 2: Group Anagrams (LeetCode 49)
 * 
 * Given an array of strings, group anagrams together.
 * 
 * Approach 1: Sort each string as key. O(n * k log k) time, O(nk) space.
 * Approach 2 (Optimal): Use character count as key. O(n * k) time, O(nk) space.
 * 
 * Production Analogy: Like grouping customer support tickets by topic - you create a
 * canonical "fingerprint" for each ticket and bucket them together.
 */
public class Problem02_GroupAnagrams {

    // Sort-based grouping
    public static List<List<String>> groupAnagramsSort(String[] strs) {
        Map<String, List<String>> map = new HashMap<>();
        for (String s : strs) {
            char[] ca = s.toCharArray();
            Arrays.sort(ca);
            String key = new String(ca);
            map.computeIfAbsent(key, k -> new ArrayList<>()).add(s);
        }
        return new ArrayList<>(map.values());
    }

    // Count-based grouping (optimal for short strings)
    public static List<List<String>> groupAnagrams(String[] strs) {
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
        System.out.println(groupAnagrams(new String[]{"eat","tea","tan","ate","nat","bat"}));
        System.out.println(groupAnagrams(new String[]{""}));
        System.out.println(groupAnagrams(new String[]{"a"}));
    }
}

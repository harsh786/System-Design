import java.util.*;

/**
 * Problem 2: Group Anagrams
 * Group strings that are anagrams of each other.
 *
 * Approach: Use sorted string as key in HashMap. All anagrams produce the same sorted key.
 * Alternative: Use character frequency array as key for O(n*k) instead of O(n*k*log(k)).
 *
 * Time Complexity: O(n * k * log(k)) where n=number of strings, k=max string length
 * Space Complexity: O(n * k)
 *
 * Production Analogy: Content deduplication in CDNs - grouping equivalent content
 * regardless of encoding order. Similar to grouping equivalent search queries.
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

    // Optimal: O(n*k) using char count as key
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

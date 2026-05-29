/**
 * Problem: Group Anagrams (LeetCode 49)
 * Approach: Sort each word as key or use char count as key
 * Complexity: O(n * k log k) time, O(n*k) space
 * Production Analogy: Content deduplication by canonical form in storage systems
 */
import java.util.*;
public class Problem04_GroupAnagrams {
    public List<List<String>> groupAnagrams(String[] strs) {
        Map<String, List<String>> map = new HashMap<>();
        for (String s : strs) {
            char[] arr = s.toCharArray(); Arrays.sort(arr);
            map.computeIfAbsent(new String(arr), k -> new ArrayList<>()).add(s);
        }
        return new ArrayList<>(map.values());
    }
    public static void main(String[] args) {
        System.out.println(new Problem04_GroupAnagrams().groupAnagrams(
            new String[]{"eat","tea","tan","ate","nat","bat"}));
    }
}

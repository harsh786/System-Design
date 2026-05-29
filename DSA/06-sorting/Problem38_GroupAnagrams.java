import java.util.*;

/**
 * Problem 38: Group Anagrams
 * 
 * Group strings that are anagrams of each other.
 * 
 * Approach: Sort each string as key, or use character count as key.
 * Time Complexity: O(n * k log k) with sort key, O(n * k) with count key
 * Space Complexity: O(n * k)
 * 
 * Production Analogy: Content deduplication in storage systems - grouping files with
 * same content hash regardless of filename.
 */
public class Problem38_GroupAnagrams {
    
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
    
    // O(n*k) approach with count key
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
        Problem38_GroupAnagrams sol = new Problem38_GroupAnagrams();
        
        String[] t1 = {"eat","tea","tan","ate","nat","bat"};
        System.out.println("Test 1: " + sol.groupAnagrams(t1));
        
        System.out.println("Test 2: " + sol.groupAnagrams(new String[]{""}));
        System.out.println("Test 3: " + sol.groupAnagrams(new String[]{"a"}));
        System.out.println("Test 4: " + sol.groupAnagramsOptimal(t1));
    }
}

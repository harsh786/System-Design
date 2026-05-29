import java.util.*;

/**
 * Problem 8: Sort Characters By Frequency
 * 
 * Sort a string in decreasing order based on character frequency.
 * 
 * Approach: Count frequencies, then bucket sort by frequency.
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Huffman encoding preparation - characters sorted by frequency
 * get shorter codes, optimizing compression ratio.
 */
public class Problem08_SortCharactersByFrequency {
    
    @SuppressWarnings("unchecked")
    public String frequencySort(String s) {
        Map<Character, Integer> freq = new HashMap<>();
        for (char c : s.toCharArray()) freq.merge(c, 1, Integer::sum);
        
        List<Character>[] buckets = new List[s.length() + 1];
        for (var entry : freq.entrySet()) {
            int f = entry.getValue();
            if (buckets[f] == null) buckets[f] = new ArrayList<>();
            buckets[f].add(entry.getKey());
        }
        
        StringBuilder sb = new StringBuilder();
        for (int i = buckets.length - 1; i >= 1; i--) {
            if (buckets[i] != null) {
                for (char c : buckets[i]) {
                    for (int j = 0; j < i; j++) sb.append(c);
                }
            }
        }
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem08_SortCharactersByFrequency sol = new Problem08_SortCharactersByFrequency();
        
        System.out.println("Test 1: " + sol.frequencySort("tree")); // "eert" or "eetr"
        System.out.println("Test 2: " + sol.frequencySort("cccaaa")); // "cccaaa" or "aaaccc"
        System.out.println("Test 3: " + sol.frequencySort("Aabb")); // "bbAa" or "bbaA"
        System.out.println("Test 4: " + sol.frequencySort("a")); // "a"
    }
}

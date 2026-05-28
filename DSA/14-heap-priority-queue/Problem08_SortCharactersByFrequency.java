import java.util.*;

/**
 * Problem 8: Sort Characters By Frequency (LeetCode 451)
 * 
 * Approach: Count frequencies, use max-heap to sort by frequency.
 * 
 * Time Complexity: O(N log K) where K = unique chars
 * Space Complexity: O(N)
 * 
 * Production Analogy: Sorting log entries by severity frequency for incident triage.
 */
public class Problem08_SortCharactersByFrequency {
    
    public String frequencySort(String s) {
        Map<Character, Integer> freq = new HashMap<>();
        for (char c : s.toCharArray()) freq.merge(c, 1, Integer::sum);
        
        PriorityQueue<Map.Entry<Character, Integer>> maxHeap = 
            new PriorityQueue<>((a, b) -> b.getValue() - a.getValue());
        maxHeap.addAll(freq.entrySet());
        
        StringBuilder sb = new StringBuilder();
        while (!maxHeap.isEmpty()) {
            Map.Entry<Character, Integer> e = maxHeap.poll();
            for (int i = 0; i < e.getValue(); i++) sb.append(e.getKey());
        }
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem08_SortCharactersByFrequency sol = new Problem08_SortCharactersByFrequency();
        System.out.println(sol.frequencySort("tree")); // "eert" or "eetr"
        System.out.println(sol.frequencySort("cccaaa")); // "cccaaa" or "aaaccc"
        System.out.println(sol.frequencySort("Aabb")); // "bbAa" or "bbaA"
    }
}

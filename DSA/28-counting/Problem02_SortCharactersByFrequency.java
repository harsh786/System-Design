/**
 * Problem: Sort Characters By Frequency (LeetCode 451)
 * Approach: Count + bucket sort
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Frequency-based content ranking in search engines
 */
import java.util.*;
public class Problem02_SortCharactersByFrequency {
    public String frequencySort(String s) {
        Map<Character, Integer> freq = new HashMap<>();
        for (char c : s.toCharArray()) freq.merge(c, 1, Integer::sum);
        List<Character>[] buckets = new List[s.length()+1];
        for (int i = 0; i < buckets.length; i++) buckets[i] = new ArrayList<>();
        for (var e : freq.entrySet()) buckets[e.getValue()].add(e.getKey());
        StringBuilder sb = new StringBuilder();
        for (int i = buckets.length-1; i >= 0; i--)
            for (char c : buckets[i]) sb.append(String.valueOf(c).repeat(i));
        return sb.toString();
    }
    public static void main(String[] args) {
        System.out.println(new Problem02_SortCharactersByFrequency().frequencySort("tree")); // eert
    }
}

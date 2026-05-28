/**
 * Problem 43: Find All Anagrams in a String
 * 
 * Find all start indices of p's anagrams in s.
 * 
 * Approach: Sliding window of size p.length() with frequency comparison.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like scanning network traffic for packets that contain
 * the same byte distribution as a known malware signature.
 */
import java.util.*;

public class Problem43_FindAllAnagrams {
    public static List<Integer> findAnagrams(String s, String p) {
        List<Integer> result = new ArrayList<>();
        if (s.length() < p.length()) return result;
        int[] count = new int[26];
        for (int i = 0; i < p.length(); i++) {
            count[p.charAt(i) - 'a']++;
            count[s.charAt(i) - 'a']--;
        }
        if (allZero(count)) result.add(0);
        for (int i = p.length(); i < s.length(); i++) {
            count[s.charAt(i) - 'a']--;
            count[s.charAt(i - p.length()) - 'a']++;
            if (allZero(count)) result.add(i - p.length() + 1);
        }
        return result;
    }

    private static boolean allZero(int[] c) { for (int v : c) if (v != 0) return false; return true; }

    public static void main(String[] args) {
        System.out.println(findAnagrams("cbaebabacd", "abc")); // [0,6]
        System.out.println(findAnagrams("abab", "ab")); // [0,1,2]
    }
}

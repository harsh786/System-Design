import java.util.*;
/**
 * Problem 14: Find All Anagrams in a String (LeetCode 438)
 * 
 * Approach: Fixed-size window of p.length(), compare frequency arrays.
 * Window invariant: window size == p.length(), check char frequency match.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like scanning log streams for specific patterns of events
 * regardless of order within a fixed time bucket.
 */
public class Problem14_FindAllAnagramsInString {
    public static List<Integer> findAnagrams(String s, String p) {
        List<Integer> result = new ArrayList<>();
        if (s.length() < p.length()) return result;
        int[] pCount = new int[26], wCount = new int[26];
        for (char c : p.toCharArray()) pCount[c - 'a']++;
        for (int i = 0; i < s.length(); i++) {
            wCount[s.charAt(i) - 'a']++;
            if (i >= p.length()) wCount[s.charAt(i - p.length()) - 'a']--;
            if (Arrays.equals(pCount, wCount)) result.add(i - p.length() + 1);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findAnagrams("cbaebabacd", "abc")); // [0, 6]
        System.out.println(findAnagrams("abab", "ab"));         // [0, 1, 2]
        System.out.println(findAnagrams("a", "ab"));            // []
    }
}

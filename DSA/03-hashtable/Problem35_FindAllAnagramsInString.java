import java.util.*;

/**
 * Problem 35: Find All Anagrams in a String
 * Find all start indices of p's anagrams in s.
 *
 * Approach: Sliding window of size p.length() with frequency comparison.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like pattern matching in network packet inspection (DPI) -
 * scanning a stream for any permutation of a signature.
 */
public class Problem35_FindAllAnagramsInString {
    public List<Integer> findAnagrams(String s, String p) {
        List<Integer> result = new ArrayList<>();
        if (s.length() < p.length()) return result;
        int[] pCount = new int[26], sCount = new int[26];
        for (char c : p.toCharArray()) pCount[c - 'a']++;
        for (int i = 0; i < s.length(); i++) {
            sCount[s.charAt(i) - 'a']++;
            if (i >= p.length()) sCount[s.charAt(i - p.length()) - 'a']--;
            if (Arrays.equals(pCount, sCount)) result.add(i - p.length() + 1);
        }
        return result;
    }

    public static void main(String[] args) {
        Problem35_FindAllAnagramsInString sol = new Problem35_FindAllAnagramsInString();
        System.out.println(sol.findAnagrams("cbaebabacd", "abc")); // [0,6]
        System.out.println(sol.findAnagrams("abab", "ab")); // [0,1,2]
        System.out.println(sol.findAnagrams("a", "ab")); // []
    }
}

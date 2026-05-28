import java.util.*;

/**
 * Problem 23: Find All Anagrams in a String (LeetCode 438)
 * 
 * Approach: Sliding window of size p.length(). Compare frequency arrays. O(n) time, O(1) space.
 * 
 * Production Analogy: Like detecting specific patterns (regardless of order) in a
 * streaming data pipeline using a fixed-size window.
 */
public class Problem23_FindAllAnagrams {

    public static List<Integer> findAnagrams(String s, String p) {
        List<Integer> result = new ArrayList<>();
        if (s.length() < p.length()) return result;
        int[] pCount = new int[26], sCount = new int[26];
        for (int i = 0; i < p.length(); i++) {
            pCount[p.charAt(i) - 'a']++;
            sCount[s.charAt(i) - 'a']++;
        }
        if (Arrays.equals(pCount, sCount)) result.add(0);
        for (int i = p.length(); i < s.length(); i++) {
            sCount[s.charAt(i) - 'a']++;
            sCount[s.charAt(i - p.length()) - 'a']--;
            if (Arrays.equals(pCount, sCount)) result.add(i - p.length() + 1);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(findAnagrams("cbaebabacd", "abc")); // [0, 6]
        System.out.println(findAnagrams("abab", "ab"));        // [0, 1, 2]
        System.out.println(findAnagrams("a", "ab"));           // []
    }
}

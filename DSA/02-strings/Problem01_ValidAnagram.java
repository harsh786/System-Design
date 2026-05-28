import java.util.*;

/**
 * Problem 1: Valid Anagram (LeetCode 242)
 * 
 * Given two strings s and t, return true if t is an anagram of s.
 * 
 * Approach 1 (Brute Force): Sort both strings and compare. O(n log n) time, O(n) space.
 * Approach 2 (Optimal): Use frequency count array. O(n) time, O(1) space (fixed 26 chars).
 * 
 * Production Analogy: Like verifying that two inventory shipments contain exactly the same
 * items - you count items in each and compare counts rather than sorting everything.
 */
public class Problem01_ValidAnagram {

    // Brute Force: Sort and compare
    public static boolean isAnagramBrute(String s, String t) {
        if (s.length() != t.length()) return false;
        char[] sa = s.toCharArray(), ta = t.toCharArray();
        Arrays.sort(sa);
        Arrays.sort(ta);
        return Arrays.equals(sa, ta);
    }

    // Optimal: Frequency count
    public static boolean isAnagram(String s, String t) {
        if (s.length() != t.length()) return false;
        int[] count = new int[26];
        for (int i = 0; i < s.length(); i++) {
            count[s.charAt(i) - 'a']++;
            count[t.charAt(i) - 'a']--;
        }
        for (int c : count) if (c != 0) return false;
        return true;
    }

    public static void main(String[] args) {
        System.out.println(isAnagram("anagram", "nagaram")); // true
        System.out.println(isAnagram("rat", "car"));         // false
        System.out.println(isAnagram("", ""));               // true
        System.out.println(isAnagram("a", "ab"));            // false
        System.out.println(isAnagramBrute("listen", "silent")); // true
    }
}

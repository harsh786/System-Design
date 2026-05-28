import java.util.*;

/**
 * Problem 24: Permutation in String (LeetCode 567)
 * 
 * Approach: Sliding window of size s1.length() over s2. O(n) time, O(1) space.
 * 
 * Production Analogy: Like detecting if a set of required fields (in any order) appears
 * in a contiguous section of a data stream.
 */
public class Problem24_PermutationInString {

    public static boolean checkInclusion(String s1, String s2) {
        if (s1.length() > s2.length()) return false;
        int[] count = new int[26];
        for (int i = 0; i < s1.length(); i++) {
            count[s1.charAt(i) - 'a']++;
            count[s2.charAt(i) - 'a']--;
        }
        if (allZero(count)) return true;
        for (int i = s1.length(); i < s2.length(); i++) {
            count[s2.charAt(i) - 'a']--;
            count[s2.charAt(i - s1.length()) - 'a']++;
            if (allZero(count)) return true;
        }
        return false;
    }

    private static boolean allZero(int[] count) {
        for (int c : count) if (c != 0) return false;
        return true;
    }

    public static void main(String[] args) {
        System.out.println(checkInclusion("ab", "eidbaooo")); // true
        System.out.println(checkInclusion("ab", "eidboaoo")); // false
        System.out.println(checkInclusion("a", "a"));         // true
    }
}

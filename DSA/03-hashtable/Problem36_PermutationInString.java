import java.util.*;

/**
 * Problem 36: Permutation in String
 * Return true if s2 contains a permutation of s1.
 *
 * Approach: Sliding window with frequency arrays (same as find anagrams but return boolean).
 *
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like detecting if a set of required config keys (in any order)
 * exists within a contiguous block of a config file.
 */
public class Problem36_PermutationInString {
    public boolean checkInclusion(String s1, String s2) {
        if (s1.length() > s2.length()) return false;
        int[] c1 = new int[26], c2 = new int[26];
        for (char c : s1.toCharArray()) c1[c - 'a']++;
        for (int i = 0; i < s2.length(); i++) {
            c2[s2.charAt(i) - 'a']++;
            if (i >= s1.length()) c2[s2.charAt(i - s1.length()) - 'a']--;
            if (Arrays.equals(c1, c2)) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        Problem36_PermutationInString sol = new Problem36_PermutationInString();
        System.out.println(sol.checkInclusion("ab", "eidbaooo")); // true
        System.out.println(sol.checkInclusion("ab", "eidboaoo")); // false
        System.out.println(sol.checkInclusion("adc", "dcda")); // true
    }
}

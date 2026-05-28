/**
 * Problem 42: Permutation in String
 * 
 * Check if s2 contains a permutation of s1.
 * 
 * Approach: Fixed-size sliding window of s1.length(), compare frequency counts.
 * Time: O(n), Space: O(1) (26 chars)
 * 
 * Production Analogy: Like detecting if a sequence of API calls in any order
 * matches a known attack pattern within a sliding time window.
 */
public class Problem42_PermutationInString {
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
    }
}

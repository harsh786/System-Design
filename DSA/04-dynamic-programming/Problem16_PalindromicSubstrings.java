/**
 * Problem 16: Palindromic Substrings
 * 
 * Count all palindromic substrings in the string.
 * 
 * Approach: Expand around center for each possible center (2n-1 centers).
 * 
 * Time: O(n^2), Space: O(1)
 * 
 * Production Analogy: Like scanning log patterns for symmetric error signatures.
 */
public class Problem16_PalindromicSubstrings {

    public static int countSubstrings(String s) {
        int count = 0;
        for (int i = 0; i < s.length(); i++) {
            count += expand(s, i, i);     // odd length
            count += expand(s, i, i + 1); // even length
        }
        return count;
    }

    private static int expand(String s, int l, int r) {
        int count = 0;
        while (l >= 0 && r < s.length() && s.charAt(l) == s.charAt(r)) {
            count++;
            l--;
            r++;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println("=== Palindromic Substrings ===");
        System.out.println(countSubstrings("abc")); // 3
        System.out.println(countSubstrings("aaa")); // 6
    }
}

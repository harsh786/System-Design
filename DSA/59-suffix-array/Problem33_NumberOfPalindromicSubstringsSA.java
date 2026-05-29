import java.util.*;

public class Problem33_NumberOfPalindromicSubstringsSA {
    // Count palindromic substrings using expand around center
    public static int countPalindromes(String s) {
        int count = 0;
        for (int i = 0; i < s.length(); i++) {
            count += expand(s, i, i);   // odd
            count += expand(s, i, i+1); // even
        }
        return count;
    }

    static int expand(String s, int l, int r) {
        int count = 0;
        while (l >= 0 && r < s.length() && s.charAt(l) == s.charAt(r)) { count++; l--; r++; }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(countPalindromes("abc")); // 3
        System.out.println(countPalindromes("aaa")); // 6
    }
}

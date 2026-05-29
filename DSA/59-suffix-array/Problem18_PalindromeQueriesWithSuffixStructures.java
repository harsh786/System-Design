import java.util.*;

public class Problem18_PalindromeQueriesWithSuffixStructures {
    // Check if substring is palindrome using LCE on s + "#" + reverse(s)
    public static boolean isPalindrome(String s, int l, int r) {
        // Direct check for simplicity (in practice use LCE)
        while (l < r) { if (s.charAt(l) != s.charAt(r)) return false; l++; r--; }
        return true;
    }

    // Find all palindromic substrings using suffix array concept
    public static List<String> findPalindromes(String s) {
        Set<String> palindromes = new TreeSet<>();
        for (int i = 0; i < s.length(); i++)
            for (int j = i; j < s.length(); j++)
                if (isPalindrome(s, i, j)) palindromes.add(s.substring(i, j+1));
        return new ArrayList<>(palindromes);
    }

    public static void main(String[] args) {
        System.out.println(findPalindromes("abacaba"));
    }
}

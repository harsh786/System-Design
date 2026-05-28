import java.util.*;

/**
 * Problem 31: Reverse Words in a String (LeetCode 151)
 * 
 * Approach: Split, filter empty, reverse. O(n) time, O(n) space.
 * 
 * Production Analogy: Like reversing the order of breadcrumb navigation.
 */
public class Problem31_ReverseWordsInString {

    public static String reverseWords(String s) {
        String[] words = s.trim().split("\\s+");
        StringBuilder sb = new StringBuilder();
        for (int i = words.length - 1; i >= 0; i--) {
            sb.append(words[i]);
            if (i > 0) sb.append(' ');
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(reverseWords("the sky is blue")); // "blue is sky the"
        System.out.println(reverseWords("  hello world  ")); // "world hello"
        System.out.println(reverseWords("a good   example")); // "example good a"
    }
}

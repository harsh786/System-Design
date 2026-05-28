import java.util.*;

/**
 * Problem 32: Reverse String (LeetCode 344)
 * 
 * Approach: Two pointers swap in-place. O(n) time, O(1) space.
 * 
 * Production Analogy: Like reversing a queue of pending jobs for LIFO processing.
 */
public class Problem32_ReverseString {

    public static void reverseString(char[] s) {
        int l = 0, r = s.length - 1;
        while (l < r) {
            char tmp = s[l]; s[l] = s[r]; s[r] = tmp;
            l++; r--;
        }
    }

    public static void main(String[] args) {
        char[] s1 = "hello".toCharArray();
        reverseString(s1);
        System.out.println(new String(s1)); // "olleh"
        
        char[] s2 = "Hannah".toCharArray();
        reverseString(s2);
        System.out.println(new String(s2)); // "hannaH"
    }
}

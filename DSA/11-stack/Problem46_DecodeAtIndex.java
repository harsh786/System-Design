import java.util.*;

/**
 * Problem 46: Decode At Index (LeetCode 880)
 * 
 * Encoded string with letters and digits (digit d repeats previous string d times).
 * Find k-th character (1-indexed).
 * 
 * Approach: First compute total decoded length. Then work backwards:
 * k %= size at each step. If k==0 and current char is letter, that's the answer.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like seeking to a specific position in a compressed log file
 * without decompressing everything - compute offsets then trace back.
 */
public class Problem46_DecodeAtIndex {

    public static String decodeAtIndex(String s, int k) {
        long size = 0;
        for (char c : s.toCharArray()) {
            if (Character.isDigit(c)) size *= (c - '0');
            else size++;
        }
        for (int i = s.length() - 1; i >= 0; i--) {
            k %= size;
            if (k == 0 && Character.isLetter(s.charAt(i))) {
                return String.valueOf(s.charAt(i));
            }
            if (Character.isDigit(s.charAt(i))) size /= (s.charAt(i) - '0');
            else size--;
        }
        return "";
    }

    public static void main(String[] args) {
        System.out.println(decodeAtIndex("leet2code3", 10)); // o
        System.out.println(decodeAtIndex("ha22", 5));         // h
        System.out.println(decodeAtIndex("a2345678999999999999999", 1)); // a
    }
}

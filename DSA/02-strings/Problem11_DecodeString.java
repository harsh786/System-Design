import java.util.*;

/**
 * Problem 11: Decode String (LeetCode 394)
 * 
 * Given encoded string like "3[a2[c]]", return "accaccacc".
 * 
 * Approach: Stack-based. Push counts and strings onto stack when seeing '['.
 * O(n * maxK) time, O(n) space.
 * 
 * Production Analogy: Like expanding templated configurations - nested templates
 * get resolved from inside out (stack-based resolution).
 */
public class Problem11_DecodeString {

    public static String decodeString(String s) {
        Deque<Integer> countStack = new ArrayDeque<>();
        Deque<StringBuilder> strStack = new ArrayDeque<>();
        StringBuilder current = new StringBuilder();
        int k = 0;
        for (char c : s.toCharArray()) {
            if (Character.isDigit(c)) {
                k = k * 10 + (c - '0');
            } else if (c == '[') {
                countStack.push(k);
                strStack.push(current);
                current = new StringBuilder();
                k = 0;
            } else if (c == ']') {
                int count = countStack.pop();
                StringBuilder prev = strStack.pop();
                for (int i = 0; i < count; i++) prev.append(current);
                current = prev;
            } else {
                current.append(c);
            }
        }
        return current.toString();
    }

    public static void main(String[] args) {
        System.out.println(decodeString("3[a]2[bc]"));   // "aaabcbc"
        System.out.println(decodeString("3[a2[c]]"));    // "accaccacc"
        System.out.println(decodeString("2[abc]3[cd]ef")); // "abcabccdcdcdef"
    }
}

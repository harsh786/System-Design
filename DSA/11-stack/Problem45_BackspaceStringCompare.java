import java.util.*;

/**
 * Problem 45: Backspace String Compare (LeetCode 844)
 * 
 * Given two strings with '#' as backspace, check if they're equal after processing.
 * 
 * Approach: Stack to build final string for each, then compare.
 * 
 * Time Complexity: O(n + m)
 * Space Complexity: O(n + m)
 * 
 * Production Analogy: Like comparing two text editor sessions - need to apply
 * all edit operations before comparing final documents.
 */
public class Problem45_BackspaceStringCompare {

    public static boolean backspaceCompare(String s, String t) {
        return build(s).equals(build(t));
    }

    private static String build(String s) {
        Deque<Character> stack = new ArrayDeque<>();
        for (char c : s.toCharArray()) {
            if (c == '#') { if (!stack.isEmpty()) stack.pop(); }
            else stack.push(c);
        }
        return stack.toString();
    }

    public static void main(String[] args) {
        System.out.println(backspaceCompare("ab#c", "ad#c")); // true
        System.out.println(backspaceCompare("ab##", "c#d#")); // true
        System.out.println(backspaceCompare("a#c", "b"));     // false
        System.out.println(backspaceCompare("", ""));         // true
    }
}

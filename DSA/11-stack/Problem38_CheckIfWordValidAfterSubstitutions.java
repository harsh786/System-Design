import java.util.*;

/**
 * Problem 38: Check If Word Is Valid After Substitutions (LeetCode 1003)
 * 
 * Check if string can be formed by inserting "abc" into "" repeatedly.
 * 
 * Approach: Stack-based. Push chars. When 'c' is found, check if top two are 'b' and 'a'.
 * If so pop them (removing one "abc" instance).
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like validating that a sequence of operations follows a
 * strict protocol pattern (e.g., SYN-SYN/ACK-ACK in TCP handshakes).
 */
public class Problem38_CheckIfWordValidAfterSubstitutions {

    public static boolean isValid(String s) {
        Deque<Character> stack = new ArrayDeque<>();
        for (char c : s.toCharArray()) {
            if (c == 'c') {
                if (stack.isEmpty() || stack.pop() != 'b') return false;
                if (stack.isEmpty() || stack.pop() != 'a') return false;
            } else {
                stack.push(c);
            }
        }
        return stack.isEmpty();
    }

    public static void main(String[] args) {
        System.out.println(isValid("aabcbc"));    // true
        System.out.println(isValid("abcabcababcc")); // true
        System.out.println(isValid("abccba"));    // false
        System.out.println(isValid("abc"));       // true
    }
}

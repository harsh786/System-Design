import java.util.*;

/**
 * Problem 18: Remove K Digits (LeetCode 402)
 * 
 * Remove k digits from number string to make smallest possible number.
 * 
 * Approach: Monotonic increasing stack. Remove digits from stack when current digit
 * is smaller (greedy - remove larger digits from left for smallest result).
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like optimizing resource allocation by removing the most
 * expensive (largest) components while maintaining order constraints.
 */
public class Problem18_RemoveKDigits {

    public static String removeKdigits(String num, int k) {
        Deque<Character> stack = new ArrayDeque<>();
        for (char c : num.toCharArray()) {
            while (k > 0 && !stack.isEmpty() && stack.peek() > c) {
                stack.pop();
                k--;
            }
            stack.push(c);
        }
        while (k > 0) { stack.pop(); k--; }
        
        StringBuilder sb = new StringBuilder();
        while (!stack.isEmpty()) sb.append(stack.pollLast());
        // Remove leading zeros
        while (sb.length() > 0 && sb.charAt(0) == '0') sb.deleteCharAt(0);
        return sb.length() == 0 ? "0" : sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(removeKdigits("1432219", 3)); // 1219
        System.out.println(removeKdigits("10200", 1));   // 200
        System.out.println(removeKdigits("10", 2));      // 0
        System.out.println(removeKdigits("9", 1));       // 0
    }
}

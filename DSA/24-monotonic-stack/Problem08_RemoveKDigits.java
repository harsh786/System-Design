import java.util.*;

/**
 * Problem 8: Remove K Digits (LeetCode 402)
 * 
 * Remove k digits from number string to make it smallest possible.
 * 
 * Monotonic Invariant: Increasing stack of digits. When a smaller digit arrives,
 * pop larger digits (uses one removal each) to keep the number minimal.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like optimizing a version string - removing unnecessary
 * high segments to get the minimum valid version.
 */
public class Problem08_RemoveKDigits {
    
    public String removeKdigits(String num, int k) {
        Deque<Character> stack = new ArrayDeque<>();
        
        for (char c : num.toCharArray()) {
            while (k > 0 && !stack.isEmpty() && stack.peek() > c) {
                stack.pop();
                k--;
            }
            stack.push(c);
        }
        // Remove remaining from top
        while (k > 0) { stack.pop(); k--; }
        
        // Build result, remove leading zeros
        StringBuilder sb = new StringBuilder();
        while (!stack.isEmpty()) sb.append(stack.pollLast());
        while (sb.length() > 0 && sb.charAt(0) == '0') sb.deleteCharAt(0);
        
        return sb.length() == 0 ? "0" : sb.toString();
    }
    
    public static void main(String[] args) {
        Problem08_RemoveKDigits sol = new Problem08_RemoveKDigits();
        
        System.out.println(sol.removeKdigits("1432219", 3)); // "1219"
        System.out.println(sol.removeKdigits("10200", 1));   // "200"
        System.out.println(sol.removeKdigits("10", 2));      // "0"
        System.out.println(sol.removeKdigits("9", 1));       // "0"
        System.out.println(sol.removeKdigits("112", 1));     // "11"
    }
}

/**
 * Problem 17: Remove K Digits (LeetCode 402)
 *
 * Greedy Choice: Use monotone stack - remove digits that are larger than the next digit.
 *
 * Time: O(n), Space: O(n)
 *
 * Production Analogy: Minimizing version numbers by removing k components.
 */
import java.util.*;
public class Problem17_RemoveKDigits {
    
    public static String removeKdigits(String num, int k) {
        Deque<Character> stack = new ArrayDeque<>();
        for (char c : num.toCharArray()) {
            while (!stack.isEmpty() && k > 0 && stack.peek() > c) {
                stack.pop(); k--;
            }
            stack.push(c);
        }
        while (k-- > 0) stack.pop();
        StringBuilder sb = new StringBuilder();
        while (!stack.isEmpty()) sb.append(stack.pollLast());
        // Remove leading zeros
        while (sb.length() > 0 && sb.charAt(0) == '0') sb.deleteCharAt(0);
        return sb.length() == 0 ? "0" : sb.toString();
    }
    
    public static void main(String[] args) {
        System.out.println(removeKdigits("1432219", 3)); // "1219"
        System.out.println(removeKdigits("10200", 1));   // "200"
        System.out.println(removeKdigits("10", 2));      // "0"
    }
}

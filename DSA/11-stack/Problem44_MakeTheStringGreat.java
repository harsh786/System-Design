import java.util.*;

/**
 * Problem 44: Make The String Great (LeetCode 1544)
 * 
 * Remove adjacent characters that are same letter but different case.
 * 
 * Approach: Stack. If top and current are same letter different case, pop. Else push.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like conflict resolution in merge operations where conflicting
 * entries (same key, different values) cancel each other out.
 */
public class Problem44_MakeTheStringGreat {

    public static String makeGood(String s) {
        Deque<Character> stack = new ArrayDeque<>();
        for (char c : s.toCharArray()) {
            if (!stack.isEmpty() && Math.abs(stack.peek() - c) == 32) {
                stack.pop();
            } else {
                stack.push(c);
            }
        }
        StringBuilder sb = new StringBuilder();
        while (!stack.isEmpty()) sb.append(stack.pollLast());
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(makeGood("leEeetcode")); // leetcode
        System.out.println(makeGood("abBAcC"));     // ""
        System.out.println(makeGood("s"));          // s
    }
}

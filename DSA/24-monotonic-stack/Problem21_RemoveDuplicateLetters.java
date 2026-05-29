import java.util.*;

/**
 * Problem 21: Remove Duplicate Letters (LeetCode 316)
 * 
 * Remove duplicate letters so every letter appears once and result is
 * lexicographically smallest.
 * 
 * Monotonic Invariant: Increasing stack of characters. Pop if current char is
 * smaller AND the popped char appears later in the string.
 * 
 * Time: O(n), Space: O(1) - 26 chars max
 * 
 * Production Analogy: Deduplication with ordering - like selecting unique
 * service versions in optimal order.
 */
public class Problem21_RemoveDuplicateLetters {
    
    public String removeDuplicateLetters(String s) {
        int[] lastIndex = new int[26];
        boolean[] inStack = new boolean[26];
        for (int i = 0; i < s.length(); i++) lastIndex[s.charAt(i) - 'a'] = i;
        
        Deque<Character> stack = new ArrayDeque<>();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (inStack[c - 'a']) continue;
            while (!stack.isEmpty() && stack.peek() > c && lastIndex[stack.peek() - 'a'] > i) {
                inStack[stack.pop() - 'a'] = false;
            }
            stack.push(c);
            inStack[c - 'a'] = true;
        }
        
        StringBuilder sb = new StringBuilder();
        while (!stack.isEmpty()) sb.append(stack.pollLast());
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem21_RemoveDuplicateLetters sol = new Problem21_RemoveDuplicateLetters();
        System.out.println(sol.removeDuplicateLetters("bcabc"));   // "abc"
        System.out.println(sol.removeDuplicateLetters("cbacdcbc"));// "acdb"
        System.out.println(sol.removeDuplicateLetters("abcd"));    // "abcd"
        System.out.println(sol.removeDuplicateLetters("aaaa"));    // "a"
    }
}

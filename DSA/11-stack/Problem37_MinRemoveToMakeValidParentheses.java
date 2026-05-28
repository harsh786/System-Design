import java.util.*;

/**
 * Problem 37: Minimum Remove to Make Valid Parentheses (LeetCode 1249)
 * 
 * Remove minimum parentheses to make string valid.
 * 
 * Approach: Stack stores indices of unmatched '('. Also track unmatched ')' indices.
 * Build result string skipping invalid indices.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like sanitizing user input in a template engine - removing
 * unmatched delimiters while preserving valid content.
 */
public class Problem37_MinRemoveToMakeValidParentheses {

    public static String minRemoveToMakeValid(String s) {
        Set<Integer> toRemove = new HashSet<>();
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) == '(') stack.push(i);
            else if (s.charAt(i) == ')') {
                if (stack.isEmpty()) toRemove.add(i);
                else stack.pop();
            }
        }
        while (!stack.isEmpty()) toRemove.add(stack.pop());
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            if (!toRemove.contains(i)) sb.append(s.charAt(i));
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(minRemoveToMakeValid("lee(t(c)o)de)")); // lee(t(c)o)de
        System.out.println(minRemoveToMakeValid("a)b(c)d"));       // ab(c)d
        System.out.println(minRemoveToMakeValid("))(("));           // ""
    }
}

import java.util.*;

/**
 * Problem 42: Maximum Nesting Depth of the Parentheses (LeetCode 1614)
 * 
 * Find max depth of nested parentheses in a VPS (valid parenthesized string).
 * 
 * Approach: Track current depth with counter. Max of all depths is answer.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like measuring maximum call stack depth in profiling tools
 * to detect potential stack overflow risks.
 */
public class Problem42_MaxNestingDepthOfParentheses {

    public static int maxDepth(String s) {
        int depth = 0, max = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') max = Math.max(max, ++depth);
            else if (c == ')') depth--;
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(maxDepth("(1+(2*3)+((8)/4))+1")); // 3
        System.out.println(maxDepth("(1)+((2))+(((3)))"));   // 3
        System.out.println(maxDepth(""));                     // 0
        System.out.println(maxDepth("1+(2*3)/(2-1)"));       // 1
    }
}

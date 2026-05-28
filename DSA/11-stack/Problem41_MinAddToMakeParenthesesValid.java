import java.util.*;

/**
 * Problem 41: Minimum Add to Make Parentheses Valid (LeetCode 921)
 * 
 * Return minimum number of parentheses to add to make string valid.
 * 
 * Approach: Track unmatched '(' and ')' counts. Each unmatched needs one addition.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Like computing the minimum number of compensating transactions
 * needed to balance an inconsistent ledger.
 */
public class Problem41_MinAddToMakeParenthesesValid {

    public static int minAddToMakeValid(String s) {
        int open = 0, close = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') open++;
            else if (open > 0) open--;
            else close++;
        }
        return open + close;
    }

    public static void main(String[] args) {
        System.out.println(minAddToMakeValid("())"));    // 1
        System.out.println(minAddToMakeValid("((("));    // 3
        System.out.println(minAddToMakeValid("()"));     // 0
        System.out.println(minAddToMakeValid("()))(("));  // 4
    }
}

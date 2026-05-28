/**
 * Problem 32: Minimum Add to Make Parentheses Valid (LeetCode 921)
 *
 * Greedy Choice: Track unmatched open and close parentheses.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Minimum patches needed to balance open/close resource handles.
 */
public class Problem32_MinAddToMakeParenthesesValid {
    
    public static int minAddToMakeValid(String s) {
        int open = 0, close = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') open++;
            else {
                if (open > 0) open--;
                else close++;
            }
        }
        return open + close;
    }
    
    public static void main(String[] args) {
        System.out.println(minAddToMakeValid("())"));   // 1
        System.out.println(minAddToMakeValid("((("));   // 3
        System.out.println(minAddToMakeValid("()"));    // 0
        System.out.println(minAddToMakeValid("()))((")); // 4
    }
}

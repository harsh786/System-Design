import java.util.*;

/**
 * Problem 24: Score of Parentheses (LeetCode 856)
 * 
 * () = 1, AB = A+B, (A) = 2*A. Compute score of balanced string.
 * 
 * Approach: Stack tracks current score at each depth. '(' pushes 0 (new level).
 * ')' pops and either adds 1 (for "()" base) or doubles inner score.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like computing nested priority scores in task schedulers -
 * deeper nesting multiplies importance, adjacent tasks add up.
 */
public class Problem24_ScoreOfParentheses {

    public static int scoreOfParentheses(String s) {
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(0); // current score
        for (char c : s.toCharArray()) {
            if (c == '(') {
                stack.push(0);
            } else {
                int inner = stack.pop();
                int outer = stack.pop();
                stack.push(outer + Math.max(2 * inner, 1));
            }
        }
        return stack.pop();
    }

    public static void main(String[] args) {
        System.out.println(scoreOfParentheses("()"));     // 1
        System.out.println(scoreOfParentheses("(())"));   // 2
        System.out.println(scoreOfParentheses("()()"));   // 2
        System.out.println(scoreOfParentheses("(()(()))")); // 6
    }
}

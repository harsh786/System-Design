import java.util.*;

/**
 * Problem 30: Validate Stack Sequences (LeetCode 946)
 * 
 * Given pushed and popped sequences, determine if they could be valid
 * push/pop operations on an initially empty stack.
 * 
 * Approach: Simulate using a stack. Push elements, then pop as many as match.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Validating operation logs - ensuring a sequence of
 * open/close operations on resources is valid.
 */
public class Problem30_ValidateStackSequences {
    
    public boolean validateStackSequences(int[] pushed, int[] popped) {
        Deque<Integer> stack = new ArrayDeque<>();
        int j = 0;
        for (int val : pushed) {
            stack.push(val);
            while (!stack.isEmpty() && stack.peek() == popped[j]) {
                stack.pop();
                j++;
            }
        }
        return stack.isEmpty();
    }
    
    public static void main(String[] args) {
        Problem30_ValidateStackSequences sol = new Problem30_ValidateStackSequences();
        
        System.out.println(sol.validateStackSequences(new int[]{1,2,3,4,5}, new int[]{4,5,3,2,1})); // true
        System.out.println(sol.validateStackSequences(new int[]{1,2,3,4,5}, new int[]{4,3,5,1,2})); // false
        System.out.println(sol.validateStackSequences(new int[]{1}, new int[]{1})); // true
    }
}

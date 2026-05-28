import java.util.*;

/**
 * Problem 21: Validate Stack Sequences (LeetCode 946)
 * 
 * Given pushed and popped sequences, check if they could be valid stack operations.
 * 
 * Approach: Simulate with a stack. Push elements from pushed array, pop whenever
 * top matches next expected popped element.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like validating that a sequence of resource acquire/release
 * operations follows proper LIFO ordering in a resource pool.
 */
public class Problem21_ValidateStackSequences {

    public static boolean validateStackSequences(int[] pushed, int[] popped) {
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
        System.out.println(validateStackSequences(new int[]{1,2,3,4,5}, new int[]{4,5,3,2,1})); // true
        System.out.println(validateStackSequences(new int[]{1,2,3,4,5}, new int[]{4,3,5,1,2})); // false
    }
}

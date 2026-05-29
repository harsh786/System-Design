/**
 * Problem: Validate Stack Sequences (LeetCode 946)
 * Approach: Simulate push/pop operations
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Validating operation sequences in undo/redo systems
 */
import java.util.*;
public class Problem17_ValidateStackSequences {
    public boolean validateStackSequences(int[] pushed, int[] popped) {
        Deque<Integer> stack = new ArrayDeque<>();
        int j = 0;
        for (int v : pushed) {
            stack.push(v);
            while (!stack.isEmpty() && stack.peek() == popped[j]) { stack.pop(); j++; }
        }
        return stack.isEmpty();
    }
    public static void main(String[] args) {
        System.out.println(new Problem17_ValidateStackSequences()
            .validateStackSequences(new int[]{1,2,3,4,5}, new int[]{4,5,3,2,1})); // true
    }
}

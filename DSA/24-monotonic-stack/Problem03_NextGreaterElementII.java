import java.util.*;

/**
 * Problem 3: Next Greater Element II (LeetCode 503)
 * 
 * Circular array - find next greater element for each element.
 * 
 * Monotonic Invariant: Decreasing stack. Traverse array twice (circular simulation).
 * Only assign results on elements that haven't found their NGE yet.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Circular buffer monitoring - like a round-robin scheduler
 * finding the next task with higher priority.
 */
public class Problem03_NextGreaterElementII {
    
    public int[] nextGreaterElements(int[] nums) {
        int n = nums.length;
        int[] result = new int[n];
        Arrays.fill(result, -1);
        Deque<Integer> stack = new ArrayDeque<>();
        
        // Traverse twice to handle circularity
        for (int i = 0; i < 2 * n; i++) {
            int num = nums[i % n];
            while (!stack.isEmpty() && nums[stack.peek()] < num) {
                result[stack.pop()] = num;
            }
            if (i < n) stack.push(i);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem03_NextGreaterElementII sol = new Problem03_NextGreaterElementII();
        
        System.out.println(Arrays.toString(sol.nextGreaterElements(new int[]{1,2,1})));
        // Expected: [2,-1,2]
        
        System.out.println(Arrays.toString(sol.nextGreaterElements(new int[]{1,2,3,4,3})));
        // Expected: [2,3,4,-1,4]
        
        System.out.println(Arrays.toString(sol.nextGreaterElements(new int[]{5,4,3,2,1})));
        // Expected: [-1,5,5,5,5]
        
        System.out.println(Arrays.toString(sol.nextGreaterElements(new int[]{1})));
        // Expected: [-1]
    }
}

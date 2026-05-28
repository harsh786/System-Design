import java.util.*;

/**
 * Problem 23: 132 Pattern (LeetCode 456)
 * 
 * Find if there exists i < j < k such that nums[i] < nums[k] < nums[j] (1-3-2 pattern).
 * 
 * Approach: Iterate from right. Maintain stack of candidates for nums[j] (monotonic decreasing).
 * Track the largest popped value as nums[k] (the "2" in 132). If nums[i] < nums[k], found pattern.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like detecting price manipulation patterns in trading systems -
 * a spike followed by a partial retracement signals potential market manipulation.
 */
public class Problem23_132Pattern {

    public static boolean find132pattern(int[] nums) {
        int n = nums.length;
        Deque<Integer> stack = new ArrayDeque<>();
        int third = Integer.MIN_VALUE; // the "2" in 132
        for (int i = n - 1; i >= 0; i--) {
            if (nums[i] < third) return true;
            while (!stack.isEmpty() && nums[i] > stack.peek()) {
                third = stack.pop();
            }
            stack.push(nums[i]);
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(find132pattern(new int[]{1,2,3,4}));   // false
        System.out.println(find132pattern(new int[]{3,1,4,2}));   // true
        System.out.println(find132pattern(new int[]{-1,3,2,0}));  // true
        System.out.println(find132pattern(new int[]{1,0,1,-4,-3})); // false
    }
}

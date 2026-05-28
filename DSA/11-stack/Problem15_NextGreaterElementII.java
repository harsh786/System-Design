import java.util.*;

/**
 * Problem 15: Next Greater Element II (LeetCode 503)
 * 
 * Circular array - find next greater element for each element.
 * 
 * Approach: Iterate through array twice (simulate circular) using monotonic stack.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like circular buffer monitoring - finding the next spike
 * in a ring buffer of metrics that wraps around.
 */
public class Problem15_NextGreaterElementII {

    public static int[] nextGreaterElements(int[] nums) {
        int n = nums.length;
        int[] result = new int[n];
        Arrays.fill(result, -1);
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i < 2 * n; i++) {
            while (!stack.isEmpty() && nums[stack.peek()] < nums[i % n]) {
                result[stack.pop()] = nums[i % n];
            }
            if (i < n) stack.push(i);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(nextGreaterElements(new int[]{1,2,1}))); // [2,-1,2]
        System.out.println(Arrays.toString(nextGreaterElements(new int[]{1,2,3,4,3}))); // [2,3,4,-1,4]
        System.out.println(Arrays.toString(nextGreaterElements(new int[]{5,4,3,2,1}))); // [-1,5,5,5,5]
    }
}

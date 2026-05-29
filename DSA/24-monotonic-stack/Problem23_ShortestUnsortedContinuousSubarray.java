import java.util.*;

/**
 * Problem 23: Shortest Unsorted Continuous Subarray (LeetCode 581)
 * 
 * Find shortest subarray that, if sorted, makes entire array sorted.
 * 
 * Monotonic Stack approach: Use increasing stack from left to find rightmost
 * out-of-order boundary, and decreasing stack from right for leftmost boundary.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the minimal set of out-of-order log entries
 * that need reordering to fix a corrupted event stream.
 */
public class Problem23_ShortestUnsortedContinuousSubarray {
    
    public int findUnsortedSubarray(int[] nums) {
        int n = nums.length;
        int left = n, right = 0;
        Deque<Integer> stack = new ArrayDeque<>();
        
        // Find left boundary: increasing stack from left
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && nums[stack.peek()] > nums[i]) {
                left = Math.min(left, stack.pop());
            }
            stack.push(i);
        }
        
        stack.clear();
        // Find right boundary: decreasing stack from right
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && nums[stack.peek()] < nums[i]) {
                right = Math.max(right, stack.pop());
            }
            stack.push(i);
        }
        
        return right > left ? right - left + 1 : 0;
    }
    
    public static void main(String[] args) {
        Problem23_ShortestUnsortedContinuousSubarray sol = new Problem23_ShortestUnsortedContinuousSubarray();
        
        System.out.println(sol.findUnsortedSubarray(new int[]{2,6,4,8,10,9,15})); // 5
        System.out.println(sol.findUnsortedSubarray(new int[]{1,2,3,4})); // 0
        System.out.println(sol.findUnsortedSubarray(new int[]{1})); // 0
        System.out.println(sol.findUnsortedSubarray(new int[]{2,1})); // 2
    }
}

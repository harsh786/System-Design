import java.util.*;

/**
 * Problem 4: Largest Rectangle in Histogram (LeetCode 84)
 * 
 * Find the largest rectangular area in a histogram.
 * 
 * Monotonic Invariant: Increasing stack of indices. When a shorter bar arrives,
 * pop and calculate area using the popped bar as height, with width determined
 * by current index and new stack top.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like capacity planning - finding the maximum sustained
 * throughput window given varying resource availability over time slots.
 */
public class Problem04_LargestRectangleInHistogram {
    
    public int largestRectangleArea(int[] heights) {
        int n = heights.length;
        Deque<Integer> stack = new ArrayDeque<>();
        int maxArea = 0;
        
        for (int i = 0; i <= n; i++) {
            int h = (i == n) ? 0 : heights[i];
            while (!stack.isEmpty() && h < heights[stack.peek()]) {
                int height = heights[stack.pop()];
                int width = stack.isEmpty() ? i : i - stack.peek() - 1;
                maxArea = Math.max(maxArea, height * width);
            }
            stack.push(i);
        }
        return maxArea;
    }
    
    public static void main(String[] args) {
        Problem04_LargestRectangleInHistogram sol = new Problem04_LargestRectangleInHistogram();
        
        System.out.println(sol.largestRectangleArea(new int[]{2,1,5,6,2,3})); // 10
        System.out.println(sol.largestRectangleArea(new int[]{2,4})); // 4
        System.out.println(sol.largestRectangleArea(new int[]{1})); // 1
        System.out.println(sol.largestRectangleArea(new int[]{1,1,1,1})); // 4
        System.out.println(sol.largestRectangleArea(new int[]{5,4,3,2,1})); // 9
    }
}

import java.util.*;

/**
 * Problem 6: Largest Rectangle in Histogram (LeetCode 84)
 * 
 * Given array of bar heights, find the largest rectangle area in the histogram.
 * 
 * Approach: Monotonic increasing stack. For each bar, pop all taller bars from stack,
 * calculating area with popped bar as the shortest bar. Width extends from
 * current stack top to current index.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like capacity planning - finding the largest contiguous block
 * of resources (servers, time slots) that can handle a minimum throughput level.
 */
public class Problem06_LargestRectangleInHistogram {

    public static int largestRectangleArea(int[] heights) {
        Deque<Integer> stack = new ArrayDeque<>();
        int maxArea = 0;
        int n = heights.length;
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
        System.out.println(largestRectangleArea(new int[]{2,1,5,6,2,3})); // 10
        System.out.println(largestRectangleArea(new int[]{2,4})); // 4
        System.out.println(largestRectangleArea(new int[]{1})); // 1
        System.out.println(largestRectangleArea(new int[]{0})); // 0
        System.out.println(largestRectangleArea(new int[]{1,1,1,1})); // 4
    }
}

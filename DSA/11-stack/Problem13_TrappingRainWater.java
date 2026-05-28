import java.util.*;

/**
 * Problem 13: Trapping Rain Water - Stack Approach (LeetCode 42)
 * 
 * Given elevation map, compute how much water it can trap after raining.
 * 
 * Approach: Monotonic decreasing stack. When we find a bar taller than stack top,
 * water is trapped between current bar and the bar below the popped element.
 * Calculate bounded water layer by layer.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like capacity planning in a pipeline - bottlenecks (low bars)
 * between high-capacity stages accumulate backpressure (trapped water).
 */
public class Problem13_TrappingRainWater {

    public static int trap(int[] height) {
        Deque<Integer> stack = new ArrayDeque<>();
        int water = 0;
        for (int i = 0; i < height.length; i++) {
            while (!stack.isEmpty() && height[i] > height[stack.peek()]) {
                int bottom = height[stack.pop()];
                if (stack.isEmpty()) break;
                int width = i - stack.peek() - 1;
                int bounded = Math.min(height[i], height[stack.peek()]) - bottom;
                water += width * bounded;
            }
            stack.push(i);
        }
        return water;
    }

    public static void main(String[] args) {
        System.out.println(trap(new int[]{0,1,0,2,1,0,1,3,2,1,2,1})); // 6
        System.out.println(trap(new int[]{4,2,0,3,2,5})); // 9
        System.out.println(trap(new int[]{1,2,3,4})); // 0
        System.out.println(trap(new int[]{})); // 0
    }
}

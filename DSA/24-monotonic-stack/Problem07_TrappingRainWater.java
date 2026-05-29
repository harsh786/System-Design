import java.util.*;

/**
 * Problem 7: Trapping Rain Water using Monotonic Stack (LeetCode 42)
 * 
 * Calculate how much water can be trapped between bars.
 * 
 * Monotonic Invariant: Decreasing stack. When we find a bar taller than stack top,
 * water is trapped between current bar and the bar below the popped element.
 * We calculate water layer by layer (horizontal approach).
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Buffer capacity analysis - how much data can be buffered
 * between processing rate valleys in a streaming pipeline.
 */
public class Problem07_TrappingRainWater {
    
    public int trap(int[] height) {
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
        Problem07_TrappingRainWater sol = new Problem07_TrappingRainWater();
        
        System.out.println(sol.trap(new int[]{0,1,0,2,1,0,1,3,2,1,2,1})); // 6
        System.out.println(sol.trap(new int[]{4,2,0,3,2,5})); // 9
        System.out.println(sol.trap(new int[]{1,2,3,4})); // 0
        System.out.println(sol.trap(new int[]{4,3,2,1})); // 0
        System.out.println(sol.trap(new int[]{5})); // 0
    }
}

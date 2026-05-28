/**
 * Problem 16: Trapping Rain Water
 * Given elevation map, compute how much water it can trap.
 * 
 * Production Analogy: Like computing buffer capacity between producer/consumer rates -
 * water trapped = backpressure accumulated between rate peaks.
 * 
 * O(n) time, O(1) space - two pointer approach
 */
public class Problem16_TrappingRainWater {

    public static int trap(int[] height) {
        int lo = 0, hi = height.length - 1, leftMax = 0, rightMax = 0, water = 0;
        while (lo < hi) {
            if (height[lo] < height[hi]) {
                leftMax = Math.max(leftMax, height[lo]);
                water += leftMax - height[lo];
                lo++;
            } else {
                rightMax = Math.max(rightMax, height[hi]);
                water += rightMax - height[hi];
                hi--;
            }
        }
        return water;
    }

    public static void main(String[] args) {
        System.out.println(trap(new int[]{0,1,0,2,1,0,1,3,2,1,2,1})); // 6
        System.out.println(trap(new int[]{4,2,0,3,2,5}));               // 9
        System.out.println(trap(new int[]{1,0,1}));                     // 1
        System.out.println(trap(new int[]{}));                           // 0
    }
}

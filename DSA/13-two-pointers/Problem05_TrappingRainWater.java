/**
 * Problem 5: Trapping Rain Water
 * 
 * Given elevation map, compute how much water it can trap after raining.
 * 
 * Approach: Two pointers with leftMax and rightMax tracking.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like calculating buffer capacity between producer/consumer
 * services where throughput varies - the "trapped" messages are queued.
 */
public class Problem05_TrappingRainWater {
    public static int trap(int[] height) {
        int left = 0, right = height.length - 1;
        int leftMax = 0, rightMax = 0, water = 0;
        while (left < right) {
            if (height[left] < height[right]) {
                leftMax = Math.max(leftMax, height[left]);
                water += leftMax - height[left];
                left++;
            } else {
                rightMax = Math.max(rightMax, height[right]);
                water += rightMax - height[right];
                right--;
            }
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

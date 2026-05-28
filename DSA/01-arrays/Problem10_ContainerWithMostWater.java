/**
 * Problem 10: Container With Most Water
 * Find two lines that together with x-axis form a container holding most water.
 * 
 * Production Analogy: Like optimizing throughput between two rate limiters -
 * the bottleneck is the smaller one, and distance matters (pipeline depth).
 * 
 * O(n) time, O(1) space - two pointers from both ends, move the shorter one.
 */
public class Problem10_ContainerWithMostWater {

    public static int maxArea(int[] height) {
        int lo = 0, hi = height.length - 1, max = 0;
        while (lo < hi) {
            max = Math.max(max, Math.min(height[lo], height[hi]) * (hi - lo));
            if (height[lo] < height[hi]) lo++;
            else hi--;
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(maxArea(new int[]{1,8,6,2,5,4,8,3,7})); // 49
        System.out.println(maxArea(new int[]{1,1}));                 // 1
        System.out.println(maxArea(new int[]{4,3,2,1,4}));           // 16
    }
}

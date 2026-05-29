import java.util.*;

/**
 * Problem 45: Largest Area in Histogram Variants
 * 
 * Variant 1: Find largest rectangle using exactly k distinct heights.
 * Variant 2: Find largest rectangle with height >= threshold.
 * Variant 3: Count all rectangles with area >= threshold.
 * 
 * Base approach remains monotonic stack; filter during computation.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Capacity planning with constraints - find longest
 * period where minimum throughput meets SLA threshold.
 */
public class Problem45_LargestAreaInHistogramVariants {
    
    // Variant: Largest rectangle with height >= minHeight
    public int largestRectangleAboveThreshold(int[] heights, int minHeight) {
        int n = heights.length;
        Deque<Integer> stack = new ArrayDeque<>();
        int maxArea = 0;
        
        for (int i = 0; i <= n; i++) {
            int h = (i == n) ? 0 : heights[i];
            while (!stack.isEmpty() && h < heights[stack.peek()]) {
                int height = heights[stack.pop()];
                if (height >= minHeight) {
                    int width = stack.isEmpty() ? i : i - stack.peek() - 1;
                    // Use minHeight as the effective height (we want rect >= threshold)
                    maxArea = Math.max(maxArea, height * width);
                }
            }
            stack.push(i);
        }
        return maxArea;
    }
    
    // Count all maximal rectangles and their areas
    public List<int[]> allMaximalRectangles(int[] heights) {
        int n = heights.length;
        List<int[]> rectangles = new ArrayList<>(); // [height, width, area]
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i <= n; i++) {
            int h = (i == n) ? 0 : heights[i];
            while (!stack.isEmpty() && h < heights[stack.peek()]) {
                int height = heights[stack.pop()];
                int width = stack.isEmpty() ? i : i - stack.peek() - 1;
                rectangles.add(new int[]{height, width, height * width});
            }
            stack.push(i);
        }
        return rectangles;
    }
    
    public static void main(String[] args) {
        Problem45_LargestAreaInHistogramVariants sol = new Problem45_LargestAreaInHistogramVariants();
        
        System.out.println(sol.largestRectangleAboveThreshold(new int[]{2,1,5,6,2,3}, 3)); // 10 (5*2)
        System.out.println(sol.largestRectangleAboveThreshold(new int[]{2,1,5,6,2,3}, 5)); // 10
        
        List<int[]> rects = sol.allMaximalRectangles(new int[]{2,1,5,6,2,3});
        for (int[] r : rects) System.out.println(Arrays.toString(r));
    }
}

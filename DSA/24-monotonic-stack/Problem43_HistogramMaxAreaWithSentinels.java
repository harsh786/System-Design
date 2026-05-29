import java.util.*;

/**
 * Problem 43: Histogram Max Area with Sentinels
 * 
 * Same as Problem 4 but using sentinel values (0-height bars at both ends)
 * to simplify the logic - no need for empty stack checks.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Adding boundary markers in data streams to simplify
 * window processing logic.
 */
public class Problem43_HistogramMaxAreaWithSentinels {
    
    public int largestRectangleArea(int[] heights) {
        int n = heights.length;
        // Create array with sentinels
        int[] h = new int[n + 2];
        System.arraycopy(heights, 0, h, 1, n);
        // h[0] = 0, h[n+1] = 0 (sentinels)
        
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(0); // left sentinel index
        int maxArea = 0;
        
        for (int i = 1; i < n + 2; i++) {
            while (h[i] < h[stack.peek()]) {
                int height = h[stack.pop()];
                int width = i - stack.peek() - 1;
                maxArea = Math.max(maxArea, height * width);
            }
            stack.push(i);
        }
        return maxArea;
    }
    
    public static void main(String[] args) {
        Problem43_HistogramMaxAreaWithSentinels sol = new Problem43_HistogramMaxAreaWithSentinels();
        
        System.out.println(sol.largestRectangleArea(new int[]{2,1,5,6,2,3})); // 10
        System.out.println(sol.largestRectangleArea(new int[]{2,4}));         // 4
        System.out.println(sol.largestRectangleArea(new int[]{1,1,1,1}));     // 4
        System.out.println(sol.largestRectangleArea(new int[]{5}));           // 5
    }
}

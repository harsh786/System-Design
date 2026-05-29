import java.util.*;

/**
 * Problem 50: Number of People That Can Be Seen in a Queue
 * 
 * Same as Problem 14 (LeetCode 1944) - included as the alternate title.
 * Person i can see person j if all between are shorter than min(heights[i], heights[j]).
 * 
 * Monotonic Invariant: Decreasing stack from right. Count pops + 1 if stack not empty.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Direct reachability in a layered architecture -
 * which components can communicate without intermediary blocking.
 */
public class Problem50_NumberOfPeopleThatCanBeSeenInQueue {
    
    public int[] canSeePersonsCount(int[] heights) {
        int n = heights.length;
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = n - 1; i >= 0; i--) {
            int count = 0;
            // Pop all shorter people (person i can see over them)
            while (!stack.isEmpty() && heights[stack.peek()] < heights[i]) {
                stack.pop();
                count++;
            }
            // If stack not empty, person i can also see the first taller/equal person
            if (!stack.isEmpty()) count++;
            result[i] = count;
            stack.push(i);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem50_NumberOfPeopleThatCanBeSeenInQueue sol = new Problem50_NumberOfPeopleThatCanBeSeenInQueue();
        
        System.out.println(Arrays.toString(sol.canSeePersonsCount(new int[]{10,6,8,5,11,9})));
        // Expected: [3,1,2,1,1,0]
        
        System.out.println(Arrays.toString(sol.canSeePersonsCount(new int[]{5,1,2,3,10})));
        // Expected: [4,1,1,1,0]
        
        System.out.println(Arrays.toString(sol.canSeePersonsCount(new int[]{3,1,5,2,4})));
        // Expected: [2,1,2,1,0]
        
        // Edge: single person
        System.out.println(Arrays.toString(sol.canSeePersonsCount(new int[]{5})));
        // Expected: [0]
        
        // Edge: all same height
        System.out.println(Arrays.toString(sol.canSeePersonsCount(new int[]{3,3,3,3})));
        // Expected: [1,1,1,0]
    }
}

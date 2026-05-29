import java.util.*;

/**
 * Problem 14: Number of Visible People in a Queue (LeetCode 1944)
 * 
 * Person i can see person j (j > i) if everyone between them is shorter than both.
 * 
 * Monotonic Invariant: Decreasing stack from right. For each person, count how many
 * they pop (can see) plus one more if stack isn't empty (blocked by taller).
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Network visibility - which downstream services can a gateway
 * directly reach without being blocked by intermediate proxies.
 */
public class Problem14_NumberOfVisiblePeopleInQueue {
    
    public int[] canSeePersonsCount(int[] heights) {
        int n = heights.length;
        int[] result = new int[n];
        Deque<Integer> stack = new ArrayDeque<>(); // decreasing stack
        
        for (int i = n - 1; i >= 0; i--) {
            int count = 0;
            while (!stack.isEmpty() && heights[i] > heights[stack.peek()]) {
                stack.pop();
                count++;
            }
            if (!stack.isEmpty()) count++; // can see the taller person blocking
            result[i] = count;
            stack.push(i);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem14_NumberOfVisiblePeopleInQueue sol = new Problem14_NumberOfVisiblePeopleInQueue();
        
        System.out.println(Arrays.toString(sol.canSeePersonsCount(new int[]{10,6,8,5,11,9})));
        // Expected: [3,1,2,1,1,0]
        
        System.out.println(Arrays.toString(sol.canSeePersonsCount(new int[]{5,1,2,3,10})));
        // Expected: [4,1,1,1,0]
    }
}

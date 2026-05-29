import java.util.*;

/**
 * Problem 25: Minimum Cost Tree From Leaf Values (LeetCode 1130)
 * 
 * Build binary tree where leaves are arr elements in order.
 * Each non-leaf = product of max leaf in left * max leaf in right subtree.
 * Minimize sum of non-leaf nodes.
 * 
 * Monotonic Stack approach: Greedily remove smallest elements first.
 * Use decreasing stack; when popping, multiply with min of neighbors.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Minimizing merge cost in a sorted-merge pipeline
 * by choosing optimal merge order.
 */
public class Problem25_MinimumCostTreeFromLeafValues {
    
    public int mctFromLeafValues(int[] arr) {
        Deque<Integer> stack = new ArrayDeque<>();
        stack.push(Integer.MAX_VALUE); // sentinel
        int cost = 0;
        
        for (int val : arr) {
            while (stack.peek() <= val) {
                int mid = stack.pop();
                cost += mid * Math.min(stack.peek(), val);
            }
            stack.push(val);
        }
        
        while (stack.size() > 2) {
            cost += stack.pop() * stack.peek();
        }
        return cost;
    }
    
    public static void main(String[] args) {
        Problem25_MinimumCostTreeFromLeafValues sol = new Problem25_MinimumCostTreeFromLeafValues();
        
        System.out.println(sol.mctFromLeafValues(new int[]{6,2,4}));   // 32
        System.out.println(sol.mctFromLeafValues(new int[]{4,11}));    // 44
        System.out.println(sol.mctFromLeafValues(new int[]{1,2,3,4}));// 20
    }
}

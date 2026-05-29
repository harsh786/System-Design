import java.util.*;

/**
 * Problem 31: Buildings With an Ocean View (LeetCode 1762)
 * 
 * Ocean is to the right. A building has ocean view if all buildings to its right
 * are shorter. Return indices of buildings with ocean view.
 * 
 * Approach: Traverse right to left, maintain running max or use decreasing stack.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Network line-of-sight - which servers have unobstructed
 * path to the internet gateway.
 */
public class Problem31_BuildingsWithOceanView {
    
    public int[] findBuildings(int[] heights) {
        Deque<Integer> stack = new ArrayDeque<>(); // decreasing stack
        
        for (int i = 0; i < heights.length; i++) {
            while (!stack.isEmpty() && heights[stack.peek()] <= heights[i]) {
                stack.pop();
            }
            stack.push(i);
        }
        
        int[] result = new int[stack.size()];
        for (int i = result.length - 1; i >= 0; i--) result[i] = stack.pop();
        return result;
    }
    
    public static void main(String[] args) {
        Problem31_BuildingsWithOceanView sol = new Problem31_BuildingsWithOceanView();
        
        System.out.println(Arrays.toString(sol.findBuildings(new int[]{4,2,3,1}))); // [0,2,3]
        System.out.println(Arrays.toString(sol.findBuildings(new int[]{4,3,2,1}))); // [0,1,2,3]
        System.out.println(Arrays.toString(sol.findBuildings(new int[]{1,3,2,4}))); // [3]
        System.out.println(Arrays.toString(sol.findBuildings(new int[]{2,2,2,2}))); // [3]
    }
}

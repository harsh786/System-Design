import java.util.*;

/**
 * Problem 47: Max Chunks To Make Sorted II (LeetCode 768)
 * 
 * General array (duplicates allowed). Same problem as 46 but harder.
 * 
 * Monotonic Stack approach: Maintain increasing stack of chunk maximums.
 * When incoming element is smaller, merge chunks by popping but keep the max.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Merging dependent microservice deployment groups.
 */
public class Problem47_MaxChunkToMakeSortedII {
    
    public int maxChunksToSorted(int[] arr) {
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int num : arr) {
            int curMax = num;
            // Merge chunks whose max > current element
            while (!stack.isEmpty() && stack.peek() > num) {
                curMax = Math.max(curMax, stack.pop());
            }
            stack.push(curMax);
        }
        return stack.size();
    }
    
    public static void main(String[] args) {
        Problem47_MaxChunkToMakeSortedII sol = new Problem47_MaxChunkToMakeSortedII();
        
        System.out.println(sol.maxChunksToSorted(new int[]{5,4,3,2,1})); // 1
        System.out.println(sol.maxChunksToSorted(new int[]{2,1,3,4,4})); // 4
        System.out.println(sol.maxChunksToSorted(new int[]{1,1,0,0,1})); // 1 (sorts to [0,0,1,1,1])
        System.out.println(sol.maxChunksToSorted(new int[]{1,2,3,4,5})); // 5
    }
}

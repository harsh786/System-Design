import java.util.*;

/**
 * Problem 46: Max Chunks To Make Sorted (LeetCode 769)
 * 
 * Array is permutation of [0, n-1]. Split into max chunks that when sorted
 * individually, result in sorted array.
 * 
 * Approach: Track running max. When max == index, we can split.
 * Monotonic stack variant: stack tracks chunk maximums.
 * 
 * Time: O(n), Space: O(1) for permutation, O(n) for stack variant
 * 
 * Production Analogy: Partitioning tasks into independent batches
 * that can be processed in parallel.
 */
public class Problem46_MaxChunkToMakeSorted {
    
    public int maxChunksToSorted(int[] arr) {
        int chunks = 0, max = 0;
        for (int i = 0; i < arr.length; i++) {
            max = Math.max(max, arr[i]);
            if (max == i) chunks++;
        }
        return chunks;
    }
    
    // Monotonic stack approach (works for general arrays too - see Problem 47)
    public int maxChunksStack(int[] arr) {
        Deque<Integer> stack = new ArrayDeque<>(); // stores chunk max values, increasing
        for (int num : arr) {
            int curMax = num;
            while (!stack.isEmpty() && stack.peek() > num) {
                curMax = Math.max(curMax, stack.pop());
            }
            stack.push(curMax);
        }
        return stack.size();
    }
    
    public static void main(String[] args) {
        Problem46_MaxChunkToMakeSorted sol = new Problem46_MaxChunkToMakeSorted();
        
        System.out.println(sol.maxChunksToSorted(new int[]{4,3,2,1,0})); // 1
        System.out.println(sol.maxChunksToSorted(new int[]{1,0,2,3,4})); // 4
        System.out.println(sol.maxChunksStack(new int[]{1,0,2,3,4}));    // 4
        System.out.println(sol.maxChunksStack(new int[]{4,3,2,1,0}));    // 1
    }
}

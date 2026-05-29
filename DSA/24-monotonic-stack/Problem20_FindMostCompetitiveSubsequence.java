import java.util.*;

/**
 * Problem 20: Find the Most Competitive Subsequence (LeetCode 1673)
 * 
 * Find subsequence of length k that is lexicographically smallest.
 * 
 * Monotonic Invariant: Increasing stack. Pop larger elements if enough remain.
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Selecting k servers with lowest latency from a sequence,
 * maintaining order.
 */
public class Problem20_FindMostCompetitiveSubsequence {
    
    public int[] mostCompetitive(int[] nums, int k) {
        Deque<Integer> stack = new ArrayDeque<>();
        int n = nums.length;
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && stack.peek() > nums[i] && stack.size() + (n - i) > k) {
                stack.pop();
            }
            if (stack.size() < k) stack.push(nums[i]);
        }
        
        int[] result = new int[k];
        for (int i = k - 1; i >= 0; i--) result[i] = stack.pop();
        return result;
    }
    
    public static void main(String[] args) {
        Problem20_FindMostCompetitiveSubsequence sol = new Problem20_FindMostCompetitiveSubsequence();
        
        System.out.println(Arrays.toString(sol.mostCompetitive(new int[]{3,5,2,6}, 2))); // [2,6]
        System.out.println(Arrays.toString(sol.mostCompetitive(new int[]{2,4,3,3,5,4,9,6}, 4))); // [2,3,3,4]
        System.out.println(Arrays.toString(sol.mostCompetitive(new int[]{1,2,3}, 3))); // [1,2,3]
    }
}

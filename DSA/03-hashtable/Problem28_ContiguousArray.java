import java.util.*;

/**
 * Problem 28: Contiguous Array
 * Find the maximum length subarray with equal number of 0s and 1s.
 *
 * Approach: Replace 0 with -1, then find longest subarray with sum 0 using prefix sum + HashMap.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like balanced load detection - finding the longest period where
 * read/write operations were perfectly balanced across replicas.
 */
public class Problem28_ContiguousArray {
    public int findMaxLength(int[] nums) {
        Map<Integer, Integer> map = new HashMap<>();
        map.put(0, -1);
        int sum = 0, maxLen = 0;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i] == 0 ? -1 : 1;
            if (map.containsKey(sum)) {
                maxLen = Math.max(maxLen, i - map.get(sum));
            } else {
                map.put(sum, i);
            }
        }
        return maxLen;
    }

    public static void main(String[] args) {
        Problem28_ContiguousArray sol = new Problem28_ContiguousArray();
        System.out.println(sol.findMaxLength(new int[]{0,1})); // 2
        System.out.println(sol.findMaxLength(new int[]{0,1,0})); // 2
        System.out.println(sol.findMaxLength(new int[]{0,0,1,0,0,0,1,1})); // 6
    }
}

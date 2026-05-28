import java.util.*;

/**
 * Problem 38: Number of Good Pairs
 * Count pairs (i,j) where nums[i] == nums[j] and i < j.
 *
 * Approach: For each number, the count of new pairs formed = current frequency before adding.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like counting matching event pairs in stream processing
 * (e.g., request-response correlation).
 */
public class Problem38_NumberOfGoodPairs {
    public int numIdenticalPairs(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        int count = 0;
        for (int n : nums) {
            count += freq.getOrDefault(n, 0);
            freq.merge(n, 1, Integer::sum);
        }
        return count;
    }

    public static void main(String[] args) {
        Problem38_NumberOfGoodPairs sol = new Problem38_NumberOfGoodPairs();
        System.out.println(sol.numIdenticalPairs(new int[]{1,2,3,1,1,3})); // 4
        System.out.println(sol.numIdenticalPairs(new int[]{1,1,1,1})); // 6
        System.out.println(sol.numIdenticalPairs(new int[]{1,2,3})); // 0
    }
}

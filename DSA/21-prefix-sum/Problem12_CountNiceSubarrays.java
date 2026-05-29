/**
 * Problem 12: Count Number of Nice Subarrays (LeetCode 1248)
 * 
 * Pattern: Transform to prefix sum of odd-count; equivalent to subarray sum equals k
 * 
 * Replace each element with 1 if odd, 0 if even. Then count subarrays summing to k.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Counting time windows containing exactly k anomaly events
 * in an event stream.
 */
import java.util.*;

public class Problem12_CountNiceSubarrays {

    public static int numberOfSubarrays(int[] nums, int k) {
        Map<Integer, Integer> prefixCount = new HashMap<>();
        prefixCount.put(0, 1);
        int oddCount = 0, result = 0;
        for (int num : nums) {
            oddCount += num % 2;
            result += prefixCount.getOrDefault(oddCount - k, 0);
            prefixCount.merge(oddCount, 1, Integer::sum);
        }
        return result;
    }

    public static void main(String[] args) {
        assert numberOfSubarrays(new int[]{1, 1, 2, 1, 1}, 3) == 2;
        assert numberOfSubarrays(new int[]{2, 4, 6}, 1) == 0;
        assert numberOfSubarrays(new int[]{2, 2, 2, 1, 2, 2, 1, 2, 2, 2}, 2) == 16;
        System.out.println("All tests passed!");
    }
}

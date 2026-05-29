/**
 * Problem: Count Number of Nice Subarrays (LeetCode 1248)
 * Approach: Transform to prefix sum of odd counts, use counting
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Counting qualifying windows in streaming data analysis
 */
import java.util.*;
public class Problem22_CountNiceSubarrays {
    public int numberOfSubarrays(int[] nums, int k) {
        Map<Integer, Integer> prefixCount = new HashMap<>();
        prefixCount.put(0, 1);
        int odds = 0, result = 0;
        for (int n : nums) {
            if (n % 2 == 1) odds++;
            result += prefixCount.getOrDefault(odds - k, 0);
            prefixCount.merge(odds, 1, Integer::sum);
        }
        return result;
    }
    public static void main(String[] args) {
        System.out.println(new Problem22_CountNiceSubarrays().numberOfSubarrays(new int[]{1,1,2,1,1}, 3)); // 2
    }
}

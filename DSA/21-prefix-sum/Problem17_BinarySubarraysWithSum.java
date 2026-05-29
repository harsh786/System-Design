/**
 * Problem 17: Binary Subarrays With Sum (LeetCode 930)
 * 
 * Pattern: Prefix sum + HashMap (or atMost sliding window)
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Counting network packets windows with exactly k flagged packets.
 */
import java.util.*;

public class Problem17_BinarySubarraysWithSum {

    public static int numSubarraysWithSum(int[] nums, int goal) {
        Map<Integer, Integer> count = new HashMap<>();
        count.put(0, 1);
        int sum = 0, result = 0;
        for (int num : nums) {
            sum += num;
            result += count.getOrDefault(sum - goal, 0);
            count.merge(sum, 1, Integer::sum);
        }
        return result;
    }

    public static void main(String[] args) {
        assert numSubarraysWithSum(new int[]{1, 0, 1, 0, 1}, 2) == 4;
        assert numSubarraysWithSum(new int[]{0, 0, 0, 0, 0}, 0) == 15;
        assert numSubarraysWithSum(new int[]{1, 1, 1}, 2) == 2;
        System.out.println("All tests passed!");
    }
}

/**
 * Problem: Frequency of the Most Frequent Element (LeetCode 1838)
 * Approach: Sort + sliding window with budget tracking
 * Complexity: O(n log n) time, O(1) space
 * Production Analogy: Resource leveling with limited budget in capacity planning
 */
import java.util.*;
public class Problem16_FrequencyOfMostFrequentElement {
    public int maxFrequency(int[] nums, int k) {
        Arrays.sort(nums);
        long total = 0;
        int left = 0, max = 1;
        for (int right = 0; right < nums.length; right++) {
            total += nums[right];
            while ((long)nums[right] * (right-left+1) - total > k) total -= nums[left++];
            max = Math.max(max, right-left+1);
        }
        return max;
    }
    public static void main(String[] args) {
        System.out.println(new Problem16_FrequencyOfMostFrequentElement().maxFrequency(new int[]{1,2,4}, 5)); // 3
    }
}

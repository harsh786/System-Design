/**
 * Problem 17: Count Number of Nice Subarrays (LeetCode 1248)
 * 
 * Approach: exactly(k) = atMost(k) - atMost(k-1). Count odd numbers in window.
 * Window invariant: number of odd elements in window <= k.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like counting time windows with exactly K anomalous events
 * for incident frequency analysis.
 */
public class Problem17_CountNumberOfNiceSubarrays {
    public static int numberOfSubarrays(int[] nums, int k) {
        return atMost(nums, k) - atMost(nums, k - 1);
    }

    private static int atMost(int[] nums, int k) {
        int left = 0, odds = 0, count = 0;
        for (int right = 0; right < nums.length; right++) {
            if (nums[right] % 2 == 1) odds++;
            while (odds > k) {
                if (nums[left] % 2 == 1) odds--;
                left++;
            }
            count += right - left + 1;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(numberOfSubarrays(new int[]{1,1,2,1,1}, 3));  // 2
        System.out.println(numberOfSubarrays(new int[]{2,4,6}, 1));       // 0
        System.out.println(numberOfSubarrays(new int[]{2,2,2,1,2,2,1,2,2,2}, 2)); // 16
    }
}

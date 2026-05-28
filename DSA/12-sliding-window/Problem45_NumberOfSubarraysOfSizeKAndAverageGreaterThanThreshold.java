/**
 * Problem 45: Number of Subarrays of Size K and Average >= Threshold (LeetCode 1343)
 * 
 * Approach: Fixed window of size k, check if sum >= threshold * k.
 * Window invariant: window size == k.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like counting how many k-minute intervals exceed
 * the SLA throughput threshold.
 */
public class Problem45_NumberOfSubarraysOfSizeKAndAverageGreaterThanThreshold {
    public static int numOfSubarrays(int[] arr, int k, int threshold) {
        int sum = 0, count = 0;
        int target = threshold * k;
        for (int i = 0; i < arr.length; i++) {
            sum += arr[i];
            if (i >= k) sum -= arr[i - k];
            if (i >= k - 1 && sum >= target) count++;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(numOfSubarrays(new int[]{2,2,2,2,5,5,5,8}, 3, 4)); // 3
        System.out.println(numOfSubarrays(new int[]{11,13,17,23,29,31,7,5,2,3}, 3, 5)); // 6
    }
}

/**
 * Problem 11: Number of Sub-arrays with Odd Sum (LeetCode 1524)
 * 
 * Pattern: Track count of even/odd prefix sums. Odd subarray sum = odd_prefix - even_prefix or vice versa.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Parity-based checksums in data pipelines where you count
 * segments with odd parity for error detection.
 */
public class Problem11_SubarraysWithOddSum {

    public static int numOfSubarrays(int[] arr) {
        int MOD = 1_000_000_007;
        int odd = 0, even = 1; // even starts at 1 for empty prefix
        int sum = 0;
        long count = 0;
        for (int num : arr) {
            sum += num;
            if (sum % 2 == 0) {
                count += odd;
                even++;
            } else {
                count += even;
                odd++;
            }
        }
        return (int) (count % MOD);
    }

    public static void main(String[] args) {
        assert numOfSubarrays(new int[]{1, 3, 5}) == 4;
        assert numOfSubarrays(new int[]{2, 4, 6}) == 0;
        assert numOfSubarrays(new int[]{1, 2, 3, 4, 5, 6, 7}) == 16;
        System.out.println("All tests passed!");
    }
}

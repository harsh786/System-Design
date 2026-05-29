/**
 * Problem 48: Number of Sub-arrays With Odd Sum (LeetCode 1524) - Alternative approach
 * 
 * Pattern: DP tracking count of subarrays ending at current index with odd/even sum.
 * If current element is odd: new odd subarrays = prev even + 1, new even = prev odd
 * If current element is even: new odd = prev odd, new even = prev even + 1
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Counting message batches with odd checksums for validation
 * in a streaming data pipeline.
 */
public class Problem48_NumberOfSubarraysWithOddSum {

    public static int numOfSubarrays(int[] arr) {
        int MOD = 1_000_000_007;
        long oddCount = 0, evenCount = 0, result = 0;
        for (int num : arr) {
            if (num % 2 == 1) {
                long newOdd = evenCount + 1;
                long newEven = oddCount;
                oddCount = newOdd;
                evenCount = newEven;
            } else {
                evenCount++;
                // oddCount stays same
            }
            result = (result + oddCount) % MOD;
        }
        return (int) result;
    }

    public static void main(String[] args) {
        assert numOfSubarrays(new int[]{1, 3, 5}) == 4;
        assert numOfSubarrays(new int[]{2, 4, 6}) == 0;
        assert numOfSubarrays(new int[]{1, 2, 3, 4, 5, 6, 7}) == 16;
        assert numOfSubarrays(new int[]{100, 100, 99, 100}) == 4;
        System.out.println("All tests passed!");
    }
}

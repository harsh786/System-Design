/**
 * Problem 32: Subarray Sums Divisible by K (LeetCode 974) - alternate implementation
 * 
 * Pattern: Same as Problem 13 but with array-based mod counting for clarity
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Network packet alignment—finding byte sequences that align
 * to word boundaries (divisible by word size).
 */
public class Problem32_SubarraySumsDivisibleByK {

    public static int subarraysDivByK(int[] nums, int k) {
        int[] freq = new int[k];
        freq[0] = 1;
        int sum = 0, count = 0;
        for (int num : nums) {
            sum = ((sum + num) % k + k) % k;
            count += freq[sum];
            freq[sum]++;
        }
        return count;
    }

    public static void main(String[] args) {
        assert subarraysDivByK(new int[]{4, 5, 0, -2, -3, 1}, 5) == 7;
        assert subarraysDivByK(new int[]{5}, 9) == 0;
        assert subarraysDivByK(new int[]{-1, 2, 9}, 2) == 2;
        assert subarraysDivByK(new int[]{0, 0, 0}, 1) == 6;
        System.out.println("All tests passed!");
    }
}

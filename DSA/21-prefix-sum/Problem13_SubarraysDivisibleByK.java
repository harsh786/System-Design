/**
 * Problem 13: Subarrays Divisible by K (LeetCode 974)
 * 
 * Pattern: Prefix sum mod k; count pairs with same remainder using nC2
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Finding message batches whose total size aligns to block
 * boundaries in a storage system for zero-copy writes.
 */
public class Problem13_SubarraysDivisibleByK {

    public static int subarraysDivByK(int[] nums, int k) {
        int[] modCount = new int[k];
        modCount[0] = 1;
        int sum = 0, count = 0;
        for (int num : nums) {
            sum += num;
            int mod = ((sum % k) + k) % k;
            count += modCount[mod];
            modCount[mod]++;
        }
        return count;
    }

    public static void main(String[] args) {
        assert subarraysDivByK(new int[]{4, 5, 0, -2, -3, 1}, 5) == 7;
        assert subarraysDivByK(new int[]{5}, 9) == 0;
        assert subarraysDivByK(new int[]{-1, 2, 9}, 2) == 2;
        System.out.println("All tests passed!");
    }
}

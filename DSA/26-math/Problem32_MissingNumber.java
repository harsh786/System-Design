/**
 * Problem 32: Missing Number
 * Given array of n distinct numbers in [0, n], find the missing one.
 *
 * Approach: XOR all indices and values; or use sum formula n*(n+1)/2 - sum.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like detecting missing sequence numbers in TCP packet streams.
 */
public class Problem32_MissingNumber {

    public static int missingNumber(int[] nums) {
        int n = nums.length;
        int expected = n * (n + 1) / 2;
        int actual = 0;
        for (int num : nums) actual += num;
        return expected - actual;
    }

    public static void main(String[] args) {
        System.out.println(missingNumber(new int[]{3,0,1}));     // 2
        System.out.println(missingNumber(new int[]{0,1}));       // 2
        System.out.println(missingNumber(new int[]{9,6,4,2,3,5,7,0,1})); // 8
        System.out.println(missingNumber(new int[]{0}));         // 1
    }
}

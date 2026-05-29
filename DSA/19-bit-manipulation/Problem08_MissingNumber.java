/**
 * Problem 8: Missing Number
 * Array contains n distinct numbers from [0, n]. Find the missing one.
 * 
 * Approach: XOR all indices [0..n] with all values. Duplicates cancel, missing remains.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Detecting missing sequence number in ordered message delivery.
 */
public class Problem08_MissingNumber {
    public static int missingNumber(int[] nums) {
        int xor = nums.length;
        for (int i = 0; i < nums.length; i++) {
            xor ^= i ^ nums[i];
        }
        return xor;
    }

    public static void main(String[] args) {
        System.out.println(missingNumber(new int[]{3,0,1})); // 2
        System.out.println(missingNumber(new int[]{0,1})); // 2
        System.out.println(missingNumber(new int[]{0})); // 1
        System.out.println(missingNumber(new int[]{9,6,4,2,3,5,7,0,1})); // 8
    }
}

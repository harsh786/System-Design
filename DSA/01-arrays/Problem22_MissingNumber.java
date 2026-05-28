/**
 * Problem 22: Missing Number
 * Given array [0..n] with one missing, find it.
 * 
 * Production Analogy: Like detecting a dropped packet in a numbered sequence -
 * use XOR or sum formula to find the gap.
 * 
 * O(n) time, O(1) space - XOR or math (sum formula)
 */
public class Problem22_MissingNumber {

    public static int missingNumber(int[] nums) {
        int xor = nums.length;
        for (int i = 0; i < nums.length; i++) xor ^= i ^ nums[i];
        return xor;
    }

    public static void main(String[] args) {
        System.out.println(missingNumber(new int[]{3,0,1}));     // 2
        System.out.println(missingNumber(new int[]{0,1}));       // 2
        System.out.println(missingNumber(new int[]{9,6,4,2,3,5,7,0,1})); // 8
    }
}

import java.util.*;

/**
 * Problem 15: Rotate Array
 * Rotate array to the right by k steps.
 * 
 * Production Analogy: Like rotating log file segments or shifting a circular buffer's read pointer.
 * 
 * O(n) time, O(1) space - reverse entire array, reverse first k, reverse rest
 */
public class Problem15_RotateArray {

    public static void rotate(int[] nums, int k) {
        k %= nums.length;
        reverse(nums, 0, nums.length - 1);
        reverse(nums, 0, k - 1);
        reverse(nums, k, nums.length - 1);
    }

    private static void reverse(int[] nums, int l, int r) {
        while (l < r) { int t = nums[l]; nums[l] = nums[r]; nums[r] = t; l++; r--; }
    }

    public static void main(String[] args) {
        int[] a = {1,2,3,4,5,6,7}; rotate(a, 3); System.out.println(Arrays.toString(a)); // [5,6,7,1,2,3,4]
        int[] b = {-1,-100,3,99}; rotate(b, 2); System.out.println(Arrays.toString(b)); // [3,99,-1,-100]
        int[] c = {1,2}; rotate(c, 3); System.out.println(Arrays.toString(c)); // [2,1]
    }
}

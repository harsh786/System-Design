import java.util.*;

/**
 * Problem 37: Squares of a Sorted Array
 * Return squares in sorted order from a sorted array (may have negatives).
 * 
 * Production Analogy: Like merging absolute-value sorted results from two 
 * partitions (negative and positive ranges) in a distributed query.
 * 
 * O(n) time, O(n) space - two pointers from both ends
 */
public class Problem37_SquaresOfASortedArray {

    public static int[] sortedSquares(int[] nums) {
        int n = nums.length, lo = 0, hi = n - 1;
        int[] result = new int[n];
        for (int k = n - 1; k >= 0; k--) {
            if (Math.abs(nums[lo]) > Math.abs(nums[hi])) {
                result[k] = nums[lo] * nums[lo]; lo++;
            } else {
                result[k] = nums[hi] * nums[hi]; hi--;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(sortedSquares(new int[]{-4,-1,0,3,10}))); // [0,1,9,16,100]
        System.out.println(Arrays.toString(sortedSquares(new int[]{-7,-3,2,3,11}))); // [4,9,9,49,121]
    }
}

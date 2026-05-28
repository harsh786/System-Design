/**
 * Problem 12: Squares of a Sorted Array
 * 
 * Given sorted array, return squares in sorted order.
 * 
 * Approach: Two pointers from ends (largest squares at extremes), fill result from back.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like merging two sorted streams of absolute-value metrics
 * from positive and negative deltas into a single sorted output.
 */
import java.util.Arrays;

public class Problem12_SquaresOfSortedArray {
    public static int[] sortedSquares(int[] nums) {
        int n = nums.length;
        int[] result = new int[n];
        int left = 0, right = n - 1, pos = n - 1;
        while (left <= right) {
            int lSq = nums[left] * nums[left];
            int rSq = nums[right] * nums[right];
            if (lSq > rSq) { result[pos--] = lSq; left++; }
            else { result[pos--] = rSq; right--; }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(sortedSquares(new int[]{-4,-1,0,3,10}))); // [0,1,9,16,100]
        System.out.println(Arrays.toString(sortedSquares(new int[]{-7,-3,2,3,11}))); // [4,9,9,49,121]
    }
}

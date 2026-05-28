/**
 * Problem 46: Next Permutation
 * 
 * Rearrange numbers to the next lexicographically greater permutation.
 * 
 * Approach: Find rightmost ascending pair, swap with next larger from right, reverse suffix.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like generating the next version number in a
 * lexicographic deployment ordering system.
 */
import java.util.Arrays;

public class Problem46_NextPermutation {
    public static void nextPermutation(int[] nums) {
        int n = nums.length, i = n - 2;
        while (i >= 0 && nums[i] >= nums[i + 1]) i--;
        if (i >= 0) {
            int j = n - 1;
            while (nums[j] <= nums[i]) j--;
            swap(nums, i, j);
        }
        reverse(nums, i + 1, n - 1);
    }

    private static void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }
    private static void reverse(int[] a, int l, int r) { while (l < r) swap(a, l++, r--); }

    public static void main(String[] args) {
        int[] a = {1,2,3}; nextPermutation(a);
        System.out.println(Arrays.toString(a)); // [1,3,2]

        int[] b = {3,2,1}; nextPermutation(b);
        System.out.println(Arrays.toString(b)); // [1,2,3]

        int[] c = {1,1,5}; nextPermutation(c);
        System.out.println(Arrays.toString(c)); // [1,5,1]
    }
}

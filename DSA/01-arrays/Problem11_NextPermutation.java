import java.util.*;

/**
 * Problem 11: Next Permutation
 * Rearrange numbers into the lexicographically next greater permutation.
 * 
 * Production Analogy: Like version numbering - finding the next sequential version
 * that's just one "step" greater than current. Used in combinatorial test generation.
 * 
 * O(n) time, O(1) space
 * Steps: 1) Find rightmost ascent i, 2) Find rightmost element > nums[i], swap, 3) Reverse suffix
 */
public class Problem11_NextPermutation {

    public static void nextPermutation(int[] nums) {
        int i = nums.length - 2;
        while (i >= 0 && nums[i] >= nums[i+1]) i--;
        if (i >= 0) {
            int j = nums.length - 1;
            while (nums[j] <= nums[i]) j--;
            int tmp = nums[i]; nums[i] = nums[j]; nums[j] = tmp;
        }
        // reverse from i+1 to end
        int lo = i + 1, hi = nums.length - 1;
        while (lo < hi) { int tmp = nums[lo]; nums[lo] = nums[hi]; nums[hi] = tmp; lo++; hi--; }
    }

    public static void main(String[] args) {
        int[] a = {1,2,3}; nextPermutation(a); System.out.println(Arrays.toString(a)); // [1,3,2]
        int[] b = {3,2,1}; nextPermutation(b); System.out.println(Arrays.toString(b)); // [1,2,3]
        int[] c = {1,1,5}; nextPermutation(c); System.out.println(Arrays.toString(c)); // [1,5,1]
        int[] d = {1,3,2}; nextPermutation(d); System.out.println(Arrays.toString(d)); // [2,1,3]
    }
}

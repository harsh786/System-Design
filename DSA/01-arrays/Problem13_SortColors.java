import java.util.*;

/**
 * Problem 13: Sort Colors (Dutch National Flag)
 * Sort array with values 0, 1, 2 in one pass.
 * 
 * Production Analogy: Like priority-based request routing - HIGH/MED/LOW priority
 * messages sorted into lanes in a single pass through a message queue.
 * 
 * O(n) time, O(1) space - three pointers (lo, mid, hi)
 */
public class Problem13_SortColors {

    public static void sortColors(int[] nums) {
        int lo = 0, mid = 0, hi = nums.length - 1;
        while (mid <= hi) {
            if (nums[mid] == 0) { swap(nums, lo++, mid++); }
            else if (nums[mid] == 1) { mid++; }
            else { swap(nums, mid, hi--); }
        }
    }

    private static void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        int[] a = {2,0,2,1,1,0}; sortColors(a); System.out.println(Arrays.toString(a)); // [0,0,1,1,2,2]
        int[] b = {2,0,1}; sortColors(b); System.out.println(Arrays.toString(b)); // [0,1,2]
        int[] c = {0}; sortColors(c); System.out.println(Arrays.toString(c)); // [0]
    }
}

/**
 * Problem: Sort Colors (LeetCode 75) - Counting Sort / Dutch National Flag
 * Approach: Count 0s, 1s, 2s then overwrite; or three-pointer partitioning
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Three-way partitioning in database query execution
 */
import java.util.*;
public class Problem50_SortColors {
    // Dutch National Flag - single pass
    public void sortColors(int[] nums) {
        int lo = 0, mid = 0, hi = nums.length - 1;
        while (mid <= hi) {
            if (nums[mid] == 0) { swap(nums, lo++, mid++); }
            else if (nums[mid] == 1) mid++;
            else { swap(nums, mid, hi--); }
        }
    }
    void swap(int[] a, int i, int j) { int t=a[i]; a[i]=a[j]; a[j]=t; }

    public static void main(String[] args) {
        int[] nums = {2,0,2,1,1,0};
        new Problem50_SortColors().sortColors(nums);
        System.out.println(Arrays.toString(nums)); // [0,0,1,1,2,2]
    }
}

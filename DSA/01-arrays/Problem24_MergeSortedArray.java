import java.util.*;

/**
 * Problem 24: Merge Sorted Array
 * Merge nums2 into nums1 (nums1 has enough space).
 * 
 * Production Analogy: Like merging two sorted event streams into a single timeline -
 * work backwards to avoid overwriting unprocessed elements.
 * 
 * O(m+n) time, O(1) space - three pointers from the end
 */
public class Problem24_MergeSortedArray {

    public static void merge(int[] nums1, int m, int[] nums2, int n) {
        int i = m - 1, j = n - 1, k = m + n - 1;
        while (j >= 0) {
            if (i >= 0 && nums1[i] > nums2[j]) nums1[k--] = nums1[i--];
            else nums1[k--] = nums2[j--];
        }
    }

    public static void main(String[] args) {
        int[] a = {1,2,3,0,0,0}; merge(a, 3, new int[]{2,5,6}, 3);
        System.out.println(Arrays.toString(a)); // [1,2,2,3,5,6]
        int[] b = {1}; merge(b, 1, new int[]{}, 0);
        System.out.println(Arrays.toString(b)); // [1]
    }
}

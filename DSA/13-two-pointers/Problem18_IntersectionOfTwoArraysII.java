/**
 * Problem 18: Intersection of Two Arrays II
 * 
 * Return intersection including duplicates.
 * 
 * Approach: Sort both, two pointers advance smaller element.
 * Time: O(n log n + m log m), Space: O(1) excluding output
 * 
 * Production Analogy: Like finding common items between two sorted inventory
 * lists from different warehouses for reconciliation.
 */
import java.util.*;

public class Problem18_IntersectionOfTwoArraysII {
    public static int[] intersect(int[] nums1, int[] nums2) {
        Arrays.sort(nums1);
        Arrays.sort(nums2);
        List<Integer> result = new ArrayList<>();
        int i = 0, j = 0;
        while (i < nums1.length && j < nums2.length) {
            if (nums1[i] == nums2[j]) { result.add(nums1[i]); i++; j++; }
            else if (nums1[i] < nums2[j]) i++;
            else j++;
        }
        return result.stream().mapToInt(Integer::intValue).toArray();
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(intersect(new int[]{1,2,2,1}, new int[]{2,2}))); // [2,2]
        System.out.println(Arrays.toString(intersect(new int[]{4,9,5}, new int[]{9,4,9,8,4}))); // [4,9]
    }
}

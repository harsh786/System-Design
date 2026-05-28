import java.util.*;

/**
 * Problem 32: Intersection of Two Arrays
 * 
 * Find unique intersection of two arrays.
 * 
 * Approach: Sort one array, binary search for each element of the other.
 * 
 * Time: O((m+n) log m), Space: O(min(m,n))
 * 
 * Production Analogy: Finding common feature flags enabled across two
 * deployment environments using sorted lookups.
 */
public class Problem32_IntersectionOfTwoArrays {
    public static int[] intersection(int[] nums1, int[] nums2) {
        Arrays.sort(nums2);
        Set<Integer> set = new HashSet<>();
        for (int n : nums1) {
            if (binarySearch(nums2, n)) set.add(n);
        }
        return set.stream().mapToInt(Integer::intValue).toArray();
    }

    private static boolean binarySearch(int[] arr, int target) {
        int lo = 0, hi = arr.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (arr[mid] == target) return true;
            else if (arr[mid] < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(intersection(new int[]{1,2,2,1}, new int[]{2,2})));     // [2]
        System.out.println(Arrays.toString(intersection(new int[]{4,9,5}, new int[]{9,4,9,8,4}))); // [4,9]
        System.out.println(Arrays.toString(intersection(new int[]{}, new int[]{1})));               // []
    }
}

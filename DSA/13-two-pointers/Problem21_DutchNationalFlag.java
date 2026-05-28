/**
 * Problem 21: Dutch National Flag (Generic version)
 * 
 * Partition array around a pivot into three regions: <pivot, ==pivot, >pivot.
 * 
 * Approach: Three pointers - same as Sort Colors but generalized.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like partitioning database records by SLA tier
 * (below/at/above threshold) for tiered storage migration.
 */
import java.util.Arrays;

public class Problem21_DutchNationalFlag {
    public static void partition(int[] arr, int pivot) {
        int low = 0, mid = 0, high = arr.length - 1;
        while (mid <= high) {
            if (arr[mid] < pivot) { swap(arr, low++, mid++); }
            else if (arr[mid] == pivot) { mid++; }
            else { swap(arr, mid, high--); }
        }
    }

    private static void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        int[] a = {3,1,4,1,5,9,2,6,5,3,5};
        partition(a, 5);
        System.out.println(Arrays.toString(a)); // elements <5, then 5s, then >5

        int[] b = {1,1,1};
        partition(b, 1);
        System.out.println(Arrays.toString(b)); // [1,1,1]
    }
}

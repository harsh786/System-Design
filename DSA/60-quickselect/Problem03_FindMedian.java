import java.util.*;

public class Problem03_FindMedian {
    /*
     * Find Median using Quickselect - O(n) average
     */
    public double findMedian(int[] nums) {
        int n = nums.length;
        if (n % 2 == 1) return quickselect(nums, 0, n - 1, n / 2);
        else {
            int a = quickselect(nums, 0, n - 1, n / 2 - 1);
            int b = quickselect(nums, 0, n - 1, n / 2);
            return (a + b) / 2.0;
        }
    }

    private int quickselect(int[] nums, int lo, int hi, int k) {
        if (lo == hi) return nums[lo];
        int pi = partition(nums, lo, hi);
        if (k == pi) return nums[k];
        else if (k < pi) return quickselect(nums, lo, pi - 1, k);
        else return quickselect(nums, pi + 1, hi, k);
    }

    private int partition(int[] nums, int lo, int hi) {
        int pivot = nums[lo + (hi - lo) / 2];
        swap(nums, lo + (hi - lo) / 2, hi);
        int s = lo;
        for (int i = lo; i < hi; i++) {
            if (nums[i] < pivot) { swap(nums, s, i); s++; }
        }
        swap(nums, s, hi);
        return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem03_FindMedian sol = new Problem03_FindMedian();
        System.out.println(sol.findMedian(new int[]{3, 1, 2, 5, 4})); // 3.0
        System.out.println(sol.findMedian(new int[]{3, 1, 2, 5})); // 2.5
    }
}

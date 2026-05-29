import java.util.*;

public class Problem07_WiggleSortII {
    /*
     * Wiggle Sort II - find median via quickselect then 3-way partition with virtual indexing
     * Time: O(n), Space: O(1)
     */
    public void wiggleSort(int[] nums) {
        int n = nums.length;
        int median = findMedian(nums);
        int left = 0, i = 0, right = n - 1;
        while (i <= right) {
            if (nums[mapIndex(i, n)] > median) {
                swap(nums, mapIndex(left++, n), mapIndex(i++, n));
            } else if (nums[mapIndex(i, n)] < median) {
                swap(nums, mapIndex(right--, n), mapIndex(i, n));
            } else {
                i++;
            }
        }
    }

    private int mapIndex(int idx, int n) { return (1 + 2 * idx) % (n | 1); }

    private int findMedian(int[] nums) {
        int n = nums.length;
        return quickselect(nums, 0, n - 1, n / 2);
    }

    private int quickselect(int[] nums, int lo, int hi, int k) {
        if (lo == hi) return nums[lo];
        int pi = partition(nums, lo, hi);
        if (pi == k) return nums[pi];
        else if (pi < k) return quickselect(nums, pi + 1, hi, k);
        else return quickselect(nums, lo, pi - 1, k);
    }

    private int partition(int[] nums, int lo, int hi) {
        int pivot = nums[hi], s = lo;
        for (int i = lo; i < hi; i++) {
            if (nums[i] < pivot) { swap(nums, s++, i); }
        }
        swap(nums, s, hi);
        return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem07_WiggleSortII sol = new Problem07_WiggleSortII();
        int[] arr = {1, 5, 1, 1, 6, 4};
        sol.wiggleSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

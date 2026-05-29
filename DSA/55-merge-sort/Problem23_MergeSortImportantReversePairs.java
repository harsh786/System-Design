import java.util.*;

public class Problem23_MergeSortImportantReversePairs {
    // Same as Problem06 - important reverse pairs where nums[i] > 2*nums[j]
    static int count(int[] nums) { return mergeSort(nums, 0, nums.length - 1); }
    
    static int mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return 0;
        int mid = (lo + hi) / 2;
        int c = mergeSort(a, lo, mid) + mergeSort(a, mid + 1, hi);
        int j = mid + 1;
        for (int i = lo; i <= mid; i++) { while (j <= hi && (long)a[i] > 2L * a[j]) j++; c += j - mid - 1; }
        int[] tmp = new int[hi - lo + 1]; int i2 = lo, j2 = mid + 1, k = 0;
        while (i2 <= mid && j2 <= hi) tmp[k++] = a[i2] <= a[j2] ? a[i2++] : a[j2++];
        while (i2 <= mid) tmp[k++] = a[i2++]; while (j2 <= hi) tmp[k++] = a[j2++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
        return c;
    }
    
    public static void main(String[] args) {
        System.out.println(count(new int[]{2, 4, 3, 5, 1})); // 3
    }
}

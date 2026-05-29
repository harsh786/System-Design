import java.util.*;

public class Problem24_MergeSortRangeSumCount {
    // Count subarrays with sum in [lower, upper] - same as Problem11
    static int countRangeSum(int[] nums, int lower, int upper) {
        long[] prefix = new long[nums.length + 1];
        for (int i = 0; i < nums.length; i++) prefix[i + 1] = prefix[i] + nums[i];
        return ms(prefix, 0, prefix.length - 1, lower, upper);
    }
    
    static int ms(long[] a, int lo, int hi, int lower, int upper) {
        if (lo >= hi) return 0;
        int mid = (lo + hi) / 2, c = ms(a, lo, mid, lower, upper) + ms(a, mid + 1, hi, lower, upper);
        int j1 = mid + 1, j2 = mid + 1;
        for (int i = lo; i <= mid; i++) { while (j1 <= hi && a[j1] - a[i] < lower) j1++; while (j2 <= hi && a[j2] - a[i] <= upper) j2++; c += j2 - j1; }
        long[] tmp = new long[hi - lo + 1]; int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) tmp[k++] = a[i] <= a[j] ? a[i++] : a[j++];
        while (i <= mid) tmp[k++] = a[i++]; while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length); return c;
    }
    
    public static void main(String[] args) {
        System.out.println(countRangeSum(new int[]{-2, 5, -1}, -2, 2)); // 3
    }
}

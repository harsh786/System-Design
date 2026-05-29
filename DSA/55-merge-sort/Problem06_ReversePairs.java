import java.util.*;

public class Problem06_ReversePairs {
    static int reversePairs(int[] nums) {
        return mergeSort(nums, 0, nums.length - 1);
    }
    
    static int mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return 0;
        int mid = (lo + hi) / 2;
        int count = mergeSort(a, lo, mid) + mergeSort(a, mid + 1, hi);
        int j = mid + 1;
        for (int i = lo; i <= mid; i++) {
            while (j <= hi && (long)a[i] > 2L * a[j]) j++;
            count += j - (mid + 1);
        }
        merge(a, lo, mid, hi);
        return count;
    }
    
    static void merge(int[] a, int lo, int mid, int hi) {
        int[] tmp = new int[hi - lo + 1];
        int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) tmp[k++] = a[i] <= a[j] ? a[i++] : a[j++];
        while (i <= mid) tmp[k++] = a[i++];
        while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
    }
    
    public static void main(String[] args) {
        System.out.println(reversePairs(new int[]{1, 3, 2, 3, 1})); // 2
    }
}

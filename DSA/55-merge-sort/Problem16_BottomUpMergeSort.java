import java.util.*;

public class Problem16_BottomUpMergeSort {
    static void sort(int[] arr) {
        int n = arr.length;
        for (int size = 1; size < n; size *= 2) {
            for (int lo = 0; lo < n - size; lo += 2 * size) {
                int mid = lo + size - 1;
                int hi = Math.min(lo + 2 * size - 1, n - 1);
                merge(arr, lo, mid, hi);
            }
        }
    }
    
    static void merge(int[] a, int lo, int mid, int hi) {
        int[] tmp = new int[hi - lo + 1]; int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) tmp[k++] = a[i] <= a[j] ? a[i++] : a[j++];
        while (i <= mid) tmp[k++] = a[i++]; while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
    }
    
    public static void main(String[] args) {
        int[] arr = {5, 3, 8, 1, 2, 7, 4, 6};
        sort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

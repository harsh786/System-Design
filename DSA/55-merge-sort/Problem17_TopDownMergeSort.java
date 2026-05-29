import java.util.*;

public class Problem17_TopDownMergeSort {
    static void sort(int[] arr) { mergeSort(arr, 0, arr.length - 1); }
    
    static void mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2;
        mergeSort(a, lo, mid);
        mergeSort(a, mid + 1, hi);
        merge(a, lo, mid, hi);
    }
    
    static void merge(int[] a, int lo, int mid, int hi) {
        int[] tmp = new int[hi - lo + 1]; int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) tmp[k++] = a[i] <= a[j] ? a[i++] : a[j++];
        while (i <= mid) tmp[k++] = a[i++]; while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
    }
    
    public static void main(String[] args) {
        int[] arr = {9, 1, 5, 3, 7, 2, 8, 4, 6};
        sort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

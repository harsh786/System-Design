import java.util.*;

public class Problem18_MergeSortWithSentinel {
    static void sort(int[] arr) { mergeSort(arr, 0, arr.length - 1); }
    
    static void mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2;
        mergeSort(a, lo, mid); mergeSort(a, mid + 1, hi);
        mergeWithSentinel(a, lo, mid, hi);
    }
    
    static void mergeWithSentinel(int[] a, int lo, int mid, int hi) {
        int n1 = mid - lo + 1, n2 = hi - mid;
        int[] L = new int[n1 + 1], R = new int[n2 + 1];
        System.arraycopy(a, lo, L, 0, n1);
        System.arraycopy(a, mid + 1, R, 0, n2);
        L[n1] = R[n2] = Integer.MAX_VALUE; // sentinels
        int i = 0, j = 0;
        for (int k = lo; k <= hi; k++)
            a[k] = L[i] <= R[j] ? L[i++] : R[j++];
    }
    
    public static void main(String[] args) {
        int[] arr = {12, 3, 7, 9, 14, 6, 11, 2};
        sort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

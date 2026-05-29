import java.util.*;

public class Problem44_TimSort {
    static final int MIN_RUN = 4;
    
    static void timSort(int[] arr) {
        int n = arr.length;
        // Step 1: Sort small runs with insertion sort
        for (int i = 0; i < n; i += MIN_RUN)
            insertionSort(arr, i, Math.min(i + MIN_RUN - 1, n - 1));
        // Step 2: Merge runs
        for (int size = MIN_RUN; size < n; size *= 2)
            for (int lo = 0; lo < n - size; lo += 2 * size)
                merge(arr, lo, lo + size - 1, Math.min(lo + 2 * size - 1, n - 1));
    }
    
    static void insertionSort(int[] a, int lo, int hi) {
        for (int i = lo + 1; i <= hi; i++) { int key = a[i], j = i - 1; while (j >= lo && a[j] > key) { a[j+1] = a[j]; j--; } a[j+1] = key; }
    }
    
    static void merge(int[] a, int lo, int mid, int hi) {
        int[] t = new int[hi-lo+1]; int i=lo,j=mid+1,k=0;
        while(i<=mid&&j<=hi) t[k++]=a[i]<=a[j]?a[i++]:a[j++];
        while(i<=mid)t[k++]=a[i++]; while(j<=hi)t[k++]=a[j++];
        System.arraycopy(t,0,a,lo,t.length);
    }
    
    public static void main(String[] args) {
        int[] arr = {5, 21, 7, 23, 19, 10, 12, 1, 3, 14, 8, 2};
        timSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

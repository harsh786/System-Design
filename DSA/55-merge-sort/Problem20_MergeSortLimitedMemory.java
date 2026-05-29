import java.util.*;

public class Problem20_MergeSortLimitedMemory {
    // Merge sort using only O(n/2) extra space
    static void sort(int[] arr) { mergeSort(arr, 0, arr.length - 1, new int[arr.length / 2 + 1]); }
    
    static void mergeSort(int[] a, int lo, int hi, int[] aux) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2;
        mergeSort(a, lo, mid, aux); mergeSort(a, mid + 1, hi, aux);
        // Copy left half to aux
        int len = mid - lo + 1;
        System.arraycopy(a, lo, aux, 0, len);
        int i = 0, j = mid + 1, k = lo;
        while (i < len && j <= hi) a[k++] = aux[i] <= a[j] ? aux[i++] : a[j++];
        while (i < len) a[k++] = aux[i++];
    }
    
    public static void main(String[] args) {
        int[] arr = {5, 2, 8, 1, 9, 3, 7, 4, 6};
        sort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

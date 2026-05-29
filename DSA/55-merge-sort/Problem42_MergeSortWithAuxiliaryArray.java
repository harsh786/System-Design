import java.util.*;

public class Problem42_MergeSortWithAuxiliaryArray {
    static int[] aux;
    
    static void sort(int[] arr) { aux = new int[arr.length]; mergeSort(arr, 0, arr.length - 1); }
    
    static void mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2; mergeSort(a, lo, mid); mergeSort(a, mid + 1, hi);
        System.arraycopy(a, lo, aux, lo, hi - lo + 1);
        int i = lo, j = mid + 1;
        for (int k = lo; k <= hi; k++) {
            if (i > mid) a[k] = aux[j++];
            else if (j > hi) a[k] = aux[i++];
            else if (aux[i] <= aux[j]) a[k] = aux[i++];
            else a[k] = aux[j++];
        }
    }
    
    public static void main(String[] args) {
        int[] arr = {8, 4, 2, 6, 1, 3, 7, 5};
        sort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

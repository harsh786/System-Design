import java.util.*;

public class Problem25_MergeSortKSortedArrays {
    static int[] mergeKArrays(int[][] arrays) {
        return divideAndMerge(arrays, 0, arrays.length - 1);
    }
    
    static int[] divideAndMerge(int[][] a, int lo, int hi) {
        if (lo == hi) return a[lo];
        int mid = (lo + hi) / 2;
        int[] left = divideAndMerge(a, lo, mid);
        int[] right = divideAndMerge(a, mid + 1, hi);
        return merge(left, right);
    }
    
    static int[] merge(int[] a, int[] b) {
        int[] r = new int[a.length + b.length]; int i = 0, j = 0, k = 0;
        while (i < a.length && j < b.length) r[k++] = a[i] <= b[j] ? a[i++] : b[j++];
        while (i < a.length) r[k++] = a[i++]; while (j < b.length) r[k++] = b[j++];
        return r;
    }
    
    public static void main(String[] args) {
        int[][] arrays = {{1, 4, 7}, {2, 5, 8}, {3, 6, 9}};
        System.out.println(Arrays.toString(mergeKArrays(arrays)));
    }
}

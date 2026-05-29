import java.util.*;

public class Problem49_LimitedComparisonSort {
    static int[] arr = {5, 2, 8, 1, 4};
    static int comparisons = 0;
    
    static int compare(int a, int b) { comparisons++; return Integer.compare(a, b); }
    
    // Merge sort - optimal O(n log n) comparisons
    static int[] mergeSort(int[] a) {
        if (a.length <= 1) return a;
        int mid = a.length / 2;
        int[] left = mergeSort(Arrays.copyOfRange(a, 0, mid));
        int[] right = mergeSort(Arrays.copyOfRange(a, mid, a.length));
        return merge(left, right);
    }
    
    static int[] merge(int[] a, int[] b) {
        int[] res = new int[a.length + b.length];
        int i = 0, j = 0, k = 0;
        while (i < a.length && j < b.length)
            res[k++] = compare(a[i], b[j]) <= 0 ? a[i++] : b[j++];
        while (i < a.length) res[k++] = a[i++];
        while (j < b.length) res[k++] = b[j++];
        return res;
    }
    
    public static void main(String[] args) {
        int[] sorted = mergeSort(arr);
        System.out.println(Arrays.toString(sorted) + " comparisons=" + comparisons);
    }
}

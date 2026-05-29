import java.util.*;

public class Problem43_InPlaceMergeSort {
    // In-place merge (concept) - uses rotation-based merge, O(n log^2 n)
    static void sort(int[] arr) { mergeSort(arr, 0, arr.length - 1); }
    
    static void mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2; mergeSort(a, lo, mid); mergeSort(a, mid + 1, hi);
        inplaceMerge(a, lo, mid, hi);
    }
    
    static void inplaceMerge(int[] a, int lo, int mid, int hi) {
        int i = lo, j = mid + 1;
        while (i <= mid && j <= hi) {
            if (a[i] <= a[j]) i++;
            else {
                int val = a[j]; // shift elements [i..j-1] right by 1
                System.arraycopy(a, i, a, i + 1, j - i);
                a[i] = val;
                i++; mid++; j++;
            }
        }
    }
    
    public static void main(String[] args) {
        int[] arr = {5, 2, 8, 1, 9, 3};
        sort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

import java.util.*;

public class Problem15_NaturalMergeSort {
    // Detects natural runs and merges them
    static void naturalMergeSort(int[] arr) {
        int n = arr.length;
        while (true) {
            int i = 0;
            boolean merged = false;
            while (i < n) {
                int start1 = i;
                while (i < n - 1 && arr[i] <= arr[i + 1]) i++;
                int end1 = i; i++;
                if (i >= n) break;
                int start2 = i;
                while (i < n - 1 && arr[i] <= arr[i + 1]) i++;
                int end2 = i; i++;
                merge(arr, start1, end1, end2);
                merged = true;
            }
            if (!merged) break;
        }
    }
    
    static void merge(int[] a, int lo, int mid, int hi) {
        int[] tmp = Arrays.copyOfRange(a, lo, hi + 1);
        int i = 0, j = mid - lo + 1, k = lo;
        while (i <= mid - lo && j < tmp.length)
            a[k++] = tmp[i] <= tmp[j] ? tmp[i++] : tmp[j++];
        while (i <= mid - lo) a[k++] = tmp[i++];
        while (j < tmp.length) a[k++] = tmp[j++];
    }
    
    public static void main(String[] args) {
        int[] arr = {3, 4, 2, 1, 7, 5, 8, 9, 0, 6};
        naturalMergeSort(arr);
        System.out.println(Arrays.toString(arr));
    }
}

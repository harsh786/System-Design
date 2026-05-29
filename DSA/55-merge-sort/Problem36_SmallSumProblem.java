import java.util.*;

public class Problem36_SmallSumProblem {
    // For each element, sum all elements to its left that are smaller
    static long smallSum(int[] arr) { return mergeSort(arr, 0, arr.length - 1); }
    
    static long mergeSort(int[] a, int lo, int hi) {
        if (lo >= hi) return 0;
        int mid = (lo + hi) / 2;
        long sum = mergeSort(a, lo, mid) + mergeSort(a, mid + 1, hi);
        int[] tmp = new int[hi - lo + 1]; int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) {
            if (a[i] < a[j]) { sum += (long)a[i] * (hi - j + 1); tmp[k++] = a[i++]; }
            else tmp[k++] = a[j++];
        }
        while (i <= mid) tmp[k++] = a[i++]; while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
        return sum;
    }
    
    public static void main(String[] args) {
        System.out.println(smallSum(new int[]{1, 3, 4, 2, 5})); // 16
    }
}

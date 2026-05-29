import java.util.*;

public class Problem23_RandomizedPivotQuicksort {
    static Random rand = new Random();

    public static void quicksort(int[] arr, int lo, int hi) {
        if (lo >= hi) return;
        int pivotIdx = lo + rand.nextInt(hi - lo + 1);
        int tmp = arr[pivotIdx]; arr[pivotIdx] = arr[hi]; arr[hi] = tmp;
        int pivot = arr[hi], i = lo;
        for (int j = lo; j < hi; j++) {
            if (arr[j] <= pivot) { tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp; i++; }
        }
        tmp = arr[i]; arr[i] = arr[hi]; arr[hi] = tmp;
        quicksort(arr, lo, i - 1);
        quicksort(arr, i + 1, hi);
    }

    public static void main(String[] args) {
        int[] arr = {5,3,8,1,9,2,7};
        quicksort(arr, 0, arr.length - 1);
        System.out.println(Arrays.toString(arr));
    }
}

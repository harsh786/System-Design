import java.util.*;

public class Problem11_RandomizedQuickselect {
    static Random rand = new Random();

    public static int quickselect(int[] arr, int k) {
        return select(arr, 0, arr.length - 1, k - 1);
    }

    static int select(int[] arr, int lo, int hi, int k) {
        if (lo == hi) return arr[lo];
        int pivotIdx = lo + rand.nextInt(hi - lo + 1);
        pivotIdx = partition(arr, lo, hi, pivotIdx);
        if (k == pivotIdx) return arr[k];
        else if (k < pivotIdx) return select(arr, lo, pivotIdx - 1, k);
        else return select(arr, pivotIdx + 1, hi, k);
    }

    static int partition(int[] arr, int lo, int hi, int pivotIdx) {
        int pivot = arr[pivotIdx];
        int tmp = arr[pivotIdx]; arr[pivotIdx] = arr[hi]; arr[hi] = tmp;
        int store = lo;
        for (int i = lo; i < hi; i++) {
            if (arr[i] < pivot) {
                tmp = arr[i]; arr[i] = arr[store]; arr[store] = tmp;
                store++;
            }
        }
        tmp = arr[store]; arr[store] = arr[hi]; arr[hi] = tmp;
        return store;
    }

    public static void main(String[] args) {
        int[] arr = {3,1,4,1,5,9,2,6};
        System.out.println("3rd smallest: " + quickselect(arr.clone(), 3)); // 2
    }
}

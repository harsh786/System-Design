import java.util.*;

public class Problem11_RandomizedPartition {
    private Random rand = new Random();

    public int randomizedPartition(int[] arr, int lo, int hi) {
        int pivotIdx = lo + rand.nextInt(hi - lo + 1);
        swap(arr, pivotIdx, hi);
        int pivot = arr[hi], s = lo;
        for (int i = lo; i < hi; i++) {
            if (arr[i] <= pivot) swap(arr, s++, i);
        }
        swap(arr, s, hi);
        return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem11_RandomizedPartition sol = new Problem11_RandomizedPartition();
        int[] arr = {10, 7, 8, 9, 1, 5};
        int pi = sol.randomizedPartition(arr, 0, arr.length - 1);
        System.out.println("Pivot index: " + pi + " Array: " + Arrays.toString(arr));
    }
}

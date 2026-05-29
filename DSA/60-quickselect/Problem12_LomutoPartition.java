import java.util.*;

public class Problem12_LomutoPartition {
    public int lomutoPartition(int[] arr, int lo, int hi) {
        int pivot = arr[hi];
        int i = lo - 1;
        for (int j = lo; j < hi; j++) {
            if (arr[j] <= pivot) { i++; swap(arr, i, j); }
        }
        swap(arr, i + 1, hi);
        return i + 1;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem12_LomutoPartition sol = new Problem12_LomutoPartition();
        int[] arr = {10, 80, 30, 90, 40, 50, 70};
        int pi = sol.lomutoPartition(arr, 0, arr.length - 1);
        System.out.println("Pivot index: " + pi + " Array: " + Arrays.toString(arr));
    }
}

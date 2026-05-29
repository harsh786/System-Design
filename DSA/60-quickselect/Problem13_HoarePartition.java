import java.util.*;

public class Problem13_HoarePartition {
    public int hoarePartition(int[] arr, int lo, int hi) {
        int pivot = arr[lo + (hi - lo) / 2];
        int i = lo - 1, j = hi + 1;
        while (true) {
            do { i++; } while (arr[i] < pivot);
            do { j--; } while (arr[j] > pivot);
            if (i >= j) return j;
            swap(arr, i, j);
        }
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem13_HoarePartition sol = new Problem13_HoarePartition();
        int[] arr = {10, 80, 30, 90, 40, 50, 70};
        int pi = sol.hoarePartition(arr, 0, arr.length - 1);
        System.out.println("Partition index: " + pi + " Array: " + Arrays.toString(arr));
    }
}

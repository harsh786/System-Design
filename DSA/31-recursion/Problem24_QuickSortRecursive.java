import java.util.*;

public class Problem24_QuickSortRecursive {
    public static void quickSort(int[] arr, int l, int r) {
        if (l >= r) return;
        int pivot = arr[r], i = l;
        for (int j = l; j < r; j++) if (arr[j] < pivot) { swap(arr, i, j); i++; }
        swap(arr, i, r);
        quickSort(arr, l, i - 1); quickSort(arr, i + 1, r);
    }
    static void swap(int[] arr, int a, int b) { int t = arr[a]; arr[a] = arr[b]; arr[b] = t; }
    public static void main(String[] args) {
        int[] arr = {5, 2, 8, 1, 9, 3};
        quickSort(arr, 0, arr.length - 1);
        System.out.println(Arrays.toString(arr));
    }
}

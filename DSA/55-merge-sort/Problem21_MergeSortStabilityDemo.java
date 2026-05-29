import java.util.*;

public class Problem21_MergeSortStabilityDemo {
    static void stableMergeSort(int[][] arr) { sort(arr, 0, arr.length - 1); }
    
    static void sort(int[][] a, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2; sort(a, lo, mid); sort(a, mid + 1, hi);
        int[][] tmp = new int[hi - lo + 1][]; int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) tmp[k++] = a[i][0] <= a[j][0] ? a[i++] : a[j++]; // <= ensures stability
        while (i <= mid) tmp[k++] = a[i++]; while (j <= hi) tmp[k++] = a[j++];
        System.arraycopy(tmp, 0, a, lo, tmp.length);
    }
    
    public static void main(String[] args) {
        int[][] arr = {{3,0},{1,1},{3,2},{2,3},{1,4}}; // [value, original_index]
        stableMergeSort(arr);
        for (int[] p : arr) System.out.println(p[0] + " (orig idx " + p[1] + ")");
        // Equal elements maintain relative order
    }
}

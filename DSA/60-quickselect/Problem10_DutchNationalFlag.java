import java.util.*;

public class Problem10_DutchNationalFlag {
    /*
     * Dutch National Flag Problem - 3-way partition around a pivot value
     * Time: O(n), Space: O(1)
     */
    public void threeWayPartition(int[] arr, int pivot) {
        int lo = 0, mid = 0, hi = arr.length - 1;
        while (mid <= hi) {
            if (arr[mid] < pivot) swap(arr, lo++, mid++);
            else if (arr[mid] > pivot) swap(arr, mid, hi--);
            else mid++;
        }
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem10_DutchNationalFlag sol = new Problem10_DutchNationalFlag();
        int[] arr = {4, 9, 4, 4, 1, 9, 4, 4, 9, 4, 4, 1, 4};
        sol.threeWayPartition(arr, 4);
        System.out.println(Arrays.toString(arr));
    }
}

import java.util.*;

public class Problem14_ThreeWayPartition {
    /*
     * 3-Way Partition (Fat Pivot) - returns [lt, gt] boundaries
     * Elements < pivot are in [lo..lt-1], == pivot in [lt..gt], > pivot in [gt+1..hi]
     */
    public int[] threeWayPartition(int[] arr, int lo, int hi, int pivot) {
        int lt = lo, i = lo, gt = hi;
        while (i <= gt) {
            if (arr[i] < pivot) swap(arr, lt++, i++);
            else if (arr[i] > pivot) swap(arr, i, gt--);
            else i++;
        }
        return new int[]{lt, gt};
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem14_ThreeWayPartition sol = new Problem14_ThreeWayPartition();
        int[] arr = {4, 9, 4, 4, 1, 9, 4, 4, 9, 4, 4, 1, 4};
        int[] bounds = sol.threeWayPartition(arr, 0, arr.length - 1, 4);
        System.out.println("lt=" + bounds[0] + " gt=" + bounds[1] + " " + Arrays.toString(arr));
    }
}

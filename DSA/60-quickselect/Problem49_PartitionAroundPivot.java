import java.util.*;

public class Problem49_PartitionAroundPivot {
    /* Partition array into three parts: < pivot, == pivot, > pivot */
    public void partitionAroundPivot(int[] arr, int pivot) {
        int lo = 0, mid = 0, hi = arr.length - 1;
        while (mid <= hi) {
            if (arr[mid] < pivot) { int t = arr[lo]; arr[lo] = arr[mid]; arr[mid] = t; lo++; mid++; }
            else if (arr[mid] > pivot) { int t = arr[mid]; arr[mid] = arr[hi]; arr[hi] = t; hi--; }
            else mid++;
        }
    }

    public static void main(String[] args) {
        Problem49_PartitionAroundPivot sol = new Problem49_PartitionAroundPivot();
        int[] arr = {9, 12, 3, 5, 14, 5, 10, 5, 2};
        sol.partitionAroundPivot(arr, 5);
        System.out.println(Arrays.toString(arr));
    }
}

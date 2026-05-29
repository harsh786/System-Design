import java.util.*;

public class Problem41_ThreeWayPartitionDutchFlag {
    public void partition(int[] arr, int lo, int hi, int pivot) {
        int lt = lo, i = lo, gt = hi;
        while (i <= gt) {
            if (arr[i] < pivot) { int t = arr[lt]; arr[lt] = arr[i]; arr[i] = t; lt++; i++; }
            else if (arr[i] > pivot) { int t = arr[gt]; arr[gt] = arr[i]; arr[i] = t; gt--; }
            else i++;
        }
    }

    public static void main(String[] args) {
        Problem41_ThreeWayPartitionDutchFlag sol = new Problem41_ThreeWayPartitionDutchFlag();
        int[] arr = {1, 2, 0, 1, 2, 0, 1};
        sol.partition(arr, 0, arr.length - 1, 1);
        System.out.println(Arrays.toString(arr));
    }
}

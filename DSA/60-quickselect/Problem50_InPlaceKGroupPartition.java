import java.util.*;

public class Problem50_InPlaceKGroupPartition {
    /* Partition array into k groups based on k-1 pivots */
    public void kGroupPartition(int[] arr, int[] pivots) {
        Arrays.sort(pivots);
        int start = 0;
        for (int p = 0; p < pivots.length; p++) {
            int boundary = start;
            for (int i = start; i < arr.length; i++) {
                if (arr[i] <= pivots[p]) {
                    int t = arr[boundary]; arr[boundary] = arr[i]; arr[i] = t;
                    boundary++;
                }
            }
            start = boundary;
        }
    }

    public static void main(String[] args) {
        Problem50_InPlaceKGroupPartition sol = new Problem50_InPlaceKGroupPartition();
        int[] arr = {9, 1, 5, 3, 7, 2, 8, 4, 6, 10};
        sol.kGroupPartition(arr, new int[]{3, 7}); // 3 groups: <=3, 4-7, >7
        System.out.println(Arrays.toString(arr));
    }
}

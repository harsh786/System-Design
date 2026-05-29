import java.util.*;

public class Problem06_CountOfSmallerNumbersAfterSelf {
    // LC 315: For each element, count elements smaller to its right
    // Approach: Use sorted list (simulated with merge sort or BIT; here using TreeMap)
    public static List<Integer> countSmaller(int[] nums) {
        int n = nums.length;
        Integer[] result = new Integer[n];
        // Use merge sort approach for O(n log n)
        int[][] arr = new int[n][2]; // val, original index
        for (int i = 0; i < n; i++) arr[i] = new int[]{nums[i], i};
        int[] count = new int[n];
        mergeSort(arr, count, 0, n - 1);
        List<Integer> res = new ArrayList<>();
        for (int c : count) res.add(c);
        return res;
    }

    private static void mergeSort(int[][] arr, int[] count, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2;
        mergeSort(arr, count, lo, mid);
        mergeSort(arr, count, mid + 1, hi);
        int[][] merged = new int[hi - lo + 1][2];
        int i = lo, j = mid + 1, k = 0;
        while (i <= mid && j <= hi) {
            if (arr[i][0] <= arr[j][0]) {
                count[arr[i][1]] += j - (mid + 1);
                merged[k++] = arr[i++];
            } else {
                merged[k++] = arr[j++];
            }
        }
        while (i <= mid) { count[arr[i][1]] += j - (mid + 1); merged[k++] = arr[i++]; }
        while (j <= hi) merged[k++] = arr[j++];
        System.arraycopy(merged, 0, arr, lo, merged.length);
    }

    public static void main(String[] args) {
        System.out.println(countSmaller(new int[]{5, 2, 6, 1})); // [2,1,1,0]
    }
}

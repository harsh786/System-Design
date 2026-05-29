import java.util.*;

public class Problem32_MergeSortCountSmallerBefore {
    // Count elements smaller than nums[i] appearing before i
    static int[] countSmallerBefore(int[] nums) {
        int n = nums.length; int[] result = new int[n];
        int[][] indexed = new int[n][2];
        for (int i = 0; i < n; i++) indexed[i] = new int[]{nums[i], i};
        // Use BIT or merge sort variant
        // Simple approach: sorted prefix
        List<Integer> sorted = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            int pos = Collections.binarySearch(sorted, nums[i]);
            if (pos < 0) pos = -(pos + 1);
            result[i] = pos;
            sorted.add(pos, nums[i]);
        }
        return result;
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(countSmallerBefore(new int[]{5, 2, 6, 1}))); // [0,0,2,0]
    }
}

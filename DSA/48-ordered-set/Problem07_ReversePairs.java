import java.util.*;

public class Problem07_ReversePairs {
    // LC 493: Count reverse pairs where i < j and nums[i] > 2*nums[j]
    static int count;

    public static int reversePairs(int[] nums) {
        count = 0;
        mergeSort(nums, 0, nums.length - 1);
        return count;
    }

    private static void mergeSort(int[] nums, int lo, int hi) {
        if (lo >= hi) return;
        int mid = (lo + hi) / 2;
        mergeSort(nums, lo, mid);
        mergeSort(nums, mid + 1, hi);
        int j = mid + 1;
        for (int i = lo; i <= mid; i++) {
            while (j <= hi && (long) nums[i] > 2L * nums[j]) j++;
            count += j - (mid + 1);
        }
        Arrays.sort(nums, lo, hi + 1);
    }

    public static void main(String[] args) {
        System.out.println(reversePairs(new int[]{1, 3, 2, 3, 1})); // 2
        System.out.println(reversePairs(new int[]{2, 4, 3, 5, 1})); // 3
    }
}

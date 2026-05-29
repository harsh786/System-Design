import java.util.*;

public class Problem20_SortArrayByParity {
    public int[] sortArrayByParity(int[] nums) {
        int lo = 0, hi = nums.length - 1;
        while (lo < hi) {
            if (nums[lo] % 2 == 0) lo++;
            else { swap(nums, lo, hi); hi--; }
        }
        return nums;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem20_SortArrayByParity sol = new Problem20_SortArrayByParity();
        System.out.println(Arrays.toString(sol.sortArrayByParity(new int[]{3,1,2,4})));
    }
}

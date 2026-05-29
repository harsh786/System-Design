import java.util.*;

public class Problem06_SortColors {
    /*
     * Sort Colors - 3-way partition (Dutch National Flag)
     * Time: O(n), Space: O(1)
     */
    public void sortColors(int[] nums) {
        int lo = 0, mid = 0, hi = nums.length - 1;
        while (mid <= hi) {
            if (nums[mid] == 0) { swap(nums, lo++, mid++); }
            else if (nums[mid] == 1) { mid++; }
            else { swap(nums, mid, hi--); }
        }
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem06_SortColors sol = new Problem06_SortColors();
        int[] arr = {2, 0, 2, 1, 1, 0};
        sol.sortColors(arr);
        System.out.println(Arrays.toString(arr)); // [0,0,1,1,2,2]
    }
}

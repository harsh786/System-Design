import java.util.*;

public class Problem01_SortColors {
    // Dutch National Flag / Counting sort for 0,1,2
    public static void sortColors(int[] nums) {
        int[] count = new int[3];
        for (int n : nums) count[n]++;
        int idx = 0;
        for (int c = 0; c < 3; c++)
            for (int i = 0; i < count[c]; i++) nums[idx++] = c;
    }

    // One-pass three-way partition
    public static void sortColorsOnePass(int[] nums) {
        int lo = 0, mid = 0, hi = nums.length - 1;
        while (mid <= hi) {
            if (nums[mid] == 0) { int t=nums[lo];nums[lo]=nums[mid];nums[mid]=t; lo++;mid++; }
            else if (nums[mid] == 2) { int t=nums[mid];nums[mid]=nums[hi];nums[hi]=t; hi--; }
            else mid++;
        }
    }

    public static void main(String[] args) {
        int[] a = {2,0,2,1,1,0};
        sortColors(a);
        System.out.println(Arrays.toString(a));
        int[] b = {2,0,1};
        sortColorsOnePass(b);
        System.out.println(Arrays.toString(b));
    }
}

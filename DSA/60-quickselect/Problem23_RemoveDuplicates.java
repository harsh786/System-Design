import java.util.*;

public class Problem23_RemoveDuplicates {
    public int removeDuplicates(int[] nums) {
        if (nums.length == 0) return 0;
        int i = 0;
        for (int j = 1; j < nums.length; j++) {
            if (nums[j] != nums[i]) nums[++i] = nums[j];
        }
        return i + 1;
    }

    public static void main(String[] args) {
        Problem23_RemoveDuplicates sol = new Problem23_RemoveDuplicates();
        int[] arr = {1, 1, 2, 2, 3};
        int len = sol.removeDuplicates(arr);
        System.out.println(len + " " + Arrays.toString(Arrays.copyOf(arr, len)));
    }
}

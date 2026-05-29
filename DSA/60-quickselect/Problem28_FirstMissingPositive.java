import java.util.*;

public class Problem28_FirstMissingPositive {
    public int firstMissingPositive(int[] nums) {
        int n = nums.length;
        for (int i = 0; i < n; i++) {
            while (nums[i] > 0 && nums[i] <= n && nums[nums[i] - 1] != nums[i]) {
                int t = nums[nums[i] - 1]; nums[nums[i] - 1] = nums[i]; nums[i] = t;
            }
        }
        for (int i = 0; i < n; i++) if (nums[i] != i + 1) return i + 1;
        return n + 1;
    }

    public static void main(String[] args) {
        Problem28_FirstMissingPositive sol = new Problem28_FirstMissingPositive();
        System.out.println(sol.firstMissingPositive(new int[]{3, 4, -1, 1})); // 2
    }
}

import java.util.*;

public class Problem02_RandomPickIndex {
    // Reservoir sampling for random pick of target index
    int[] nums;
    Random rand;

    public Problem02_RandomPickIndex(int[] nums) {
        this.nums = nums;
        this.rand = new Random();
    }

    public int pick(int target) {
        int count = 0, result = -1;
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] == target) {
                count++;
                if (rand.nextInt(count) == 0) result = i;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        int[] nums = {1, 2, 3, 3, 3};
        Problem02_RandomPickIndex sol = new Problem02_RandomPickIndex(nums);
        System.out.println(sol.pick(3)); // random index among 2,3,4
        System.out.println(sol.pick(1)); // 0
    }
}

import java.util.*;

public class Problem28_CombinationSumIV {
    private Map<Integer, Integer> memo = new HashMap<>();

    public int combinationSum4(int[] nums, int target) {
        if (target == 0) return 1;
        if (target < 0) return 0;
        if (memo.containsKey(target)) return memo.get(target);
        int count = 0;
        for (int num : nums) count += combinationSum4(nums, target - num);
        memo.put(target, count);
        return count;
    }

    public static void main(String[] args) {
        Problem28_CombinationSumIV sol = new Problem28_CombinationSumIV();
        System.out.println(sol.combinationSum4(new int[]{1,2,3}, 4)); // 7
    }
}

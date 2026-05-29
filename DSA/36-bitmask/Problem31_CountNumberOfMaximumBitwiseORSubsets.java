public class Problem31_CountNumberOfMaximumBitwiseORSubsets {
    int count = 0;

    public int countMaxOrSubsets(int[] nums) {
        int maxOr = 0;
        for (int n : nums) maxOr |= n;
        dfs(nums, 0, 0, maxOr);
        return count;
    }

    private void dfs(int[] nums, int idx, int cur, int target) {
        if (idx == nums.length) { if (cur == target) count++; return; }
        dfs(nums, idx + 1, cur | nums[idx], target);
        dfs(nums, idx + 1, cur, target);
    }

    public static void main(String[] args) {
        System.out.println(new Problem31_CountNumberOfMaximumBitwiseORSubsets().countMaxOrSubsets(new int[]{3,1}));
    }
}

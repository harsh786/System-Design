public class Problem20_TwentyFourGame {
    public boolean judgePoint24(int[] cards) {
        double[] arr = new double[4];
        for (int i = 0; i < 4; i++) arr[i] = cards[i];
        return solve(arr);
    }

    private boolean solve(double[] nums) {
        if (nums.length == 1) return Math.abs(nums[0] - 24) < 1e-6;
        for (int i = 0; i < nums.length; i++) for (int j = 0; j < nums.length; j++) {
            if (i == j) continue;
            double[] next = new double[nums.length - 1];
            int idx = 0;
            for (int k = 0; k < nums.length; k++) if (k != i && k != j) next[idx++] = nums[k];
            for (int op = 0; op < 4; op++) {
                if (op == 0) next[idx] = nums[i] + nums[j];
                else if (op == 1) next[idx] = nums[i] - nums[j];
                else if (op == 2) next[idx] = nums[i] * nums[j];
                else { if (Math.abs(nums[j]) < 1e-6) continue; next[idx] = nums[i] / nums[j]; }
                if (solve(next)) return true;
            }
        }
        return false;
    }

    public static void main(String[] args) { System.out.println(new Problem20_TwentyFourGame().judgePoint24(new int[]{4,1,8,7})); }
}

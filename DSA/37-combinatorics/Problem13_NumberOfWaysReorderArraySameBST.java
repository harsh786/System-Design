import java.util.*;

public class Problem13_NumberOfWaysReorderArraySameBST {
    static final long MOD = 1_000_000_007;
    long[][] comb;

    public int numOfWays(int[] nums) {
        int n = nums.length;
        comb = new long[n+1][n+1];
        for (int i = 0; i <= n; i++) { comb[i][0] = 1; for (int j = 1; j <= i; j++) comb[i][j] = (comb[i-1][j-1] + comb[i-1][j]) % MOD; }
        List<Integer> list = new ArrayList<>();
        for (int x : nums) list.add(x);
        return (int)((dfs(list) - 1 + MOD) % MOD);
    }

    private long dfs(List<Integer> nums) {
        if (nums.size() <= 2) return 1;
        int root = nums.get(0);
        List<Integer> left = new ArrayList<>(), right = new ArrayList<>();
        for (int i = 1; i < nums.size(); i++) { if (nums.get(i) < root) left.add(nums.get(i)); else right.add(nums.get(i)); }
        long l = dfs(left), r = dfs(right);
        return comb[left.size() + right.size()][left.size()] % MOD * l % MOD * r % MOD;
    }

    public static void main(String[] args) {
        System.out.println(new Problem13_NumberOfWaysReorderArraySameBST().numOfWays(new int[]{3,4,5,1,2}));
    }
}

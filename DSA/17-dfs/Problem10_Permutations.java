import java.util.*;

/**
 * Problem: Permutations (LeetCode 46)
 * Approach: DFS backtracking with visited array
 * Time: O(N!*N), Space: O(N)
 * Production Analogy: Generating all possible task execution orderings for scheduling optimization
 */
public class Problem10_Permutations {
    public List<List<Integer>> permute(int[] nums) {
        List<List<Integer>> res = new ArrayList<>();
        dfs(nums, new boolean[nums.length], new ArrayList<>(), res);
        return res;
    }

    private void dfs(int[] nums, boolean[] used, List<Integer> path, List<List<Integer>> res) {
        if (path.size() == nums.length) { res.add(new ArrayList<>(path)); return; }
        for (int i = 0; i < nums.length; i++) {
            if (used[i]) continue;
            used[i] = true;
            path.add(nums[i]);
            dfs(nums, used, path, res);
            path.remove(path.size() - 1);
            used[i] = false;
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem10_Permutations().permute(new int[]{1,2,3}));
    }
}

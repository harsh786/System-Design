import java.util.*;

/**
 * Problem: Subsets (LeetCode 78)
 * Approach: DFS backtracking - at each index, include or exclude element
 * Time: O(N*2^N), Space: O(N)
 * Production Analogy: Feature flag combination testing - generating all possible flag configurations
 */
public class Problem09_Subsets {
    public List<List<Integer>> subsets(int[] nums) {
        List<List<Integer>> res = new ArrayList<>();
        dfs(nums, 0, new ArrayList<>(), res);
        return res;
    }

    private void dfs(int[] nums, int start, List<Integer> path, List<List<Integer>> res) {
        res.add(new ArrayList<>(path));
        for (int i = start; i < nums.length; i++) {
            path.add(nums[i]);
            dfs(nums, i + 1, path, res);
            path.remove(path.size() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem09_Subsets().subsets(new int[]{1,2,3}));
    }
}

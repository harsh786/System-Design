import java.util.*;

/**
 * Problem: Combination Sum (LeetCode 39)
 * Approach: DFS backtracking allowing reuse of same element
 * Time: O(N^(T/M)) where T=target, M=min candidate, Space: O(T/M)
 * Production Analogy: Resource allocation - finding combinations of instance types to meet capacity
 */
public class Problem11_CombinationSum {
    public List<List<Integer>> combinationSum(int[] candidates, int target) {
        List<List<Integer>> res = new ArrayList<>();
        Arrays.sort(candidates);
        dfs(candidates, target, 0, new ArrayList<>(), res);
        return res;
    }

    private void dfs(int[] cands, int remain, int start, List<Integer> path, List<List<Integer>> res) {
        if (remain == 0) { res.add(new ArrayList<>(path)); return; }
        for (int i = start; i < cands.length && cands[i] <= remain; i++) {
            path.add(cands[i]);
            dfs(cands, remain - cands[i], i, path, res);
            path.remove(path.size() - 1);
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem11_CombinationSum().combinationSum(new int[]{2,3,6,7}, 7));
    }
}

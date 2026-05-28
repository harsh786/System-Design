import java.util.*;

/**
 * Problem: Path Sum II (LeetCode 113)
 * Approach: DFS backtracking collecting all root-to-leaf paths matching target
 * Time: O(N^2) worst case, Space: O(N)
 * Production Analogy: Finding all valid routing paths with specific latency budgets
 */
public class Problem14_PathSumII {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<List<Integer>> pathSum(TreeNode root, int targetSum) {
        List<List<Integer>> res = new ArrayList<>();
        dfs(root, targetSum, new ArrayList<>(), res);
        return res;
    }

    private void dfs(TreeNode node, int remain, List<Integer> path, List<List<Integer>> res) {
        if (node == null) return;
        path.add(node.val);
        if (node.left == null && node.right == null && remain == node.val) res.add(new ArrayList<>(path));
        dfs(node.left, remain - node.val, path, res);
        dfs(node.right, remain - node.val, path, res);
        path.remove(path.size() - 1);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(5);
        root.left = new TreeNode(4); root.right = new TreeNode(8);
        root.left.left = new TreeNode(11);
        root.left.left.left = new TreeNode(7); root.left.left.right = new TreeNode(2);
        System.out.println(new Problem14_PathSumII().pathSum(root, 22));
    }
}

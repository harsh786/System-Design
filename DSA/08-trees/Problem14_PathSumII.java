import java.util.*;
/**
 * Problem 14: Path Sum II (LeetCode 113)
 * 
 * Approach: DFS backtracking - maintain current path, add to result when leaf with target met.
 * Time: O(n^2) worst case (copying paths), Space: O(n)
 * 
 * Production Analogy: Finding all request paths through microservices that sum to a specific cost.
 */
public class Problem14_PathSumII {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<List<Integer>> pathSum(TreeNode root, int targetSum) {
        List<List<Integer>> result = new ArrayList<>();
        dfs(root, targetSum, new ArrayList<>(), result);
        return result;
    }

    private static void dfs(TreeNode node, int remain, List<Integer> path, List<List<Integer>> result) {
        if (node == null) return;
        path.add(node.val);
        if (node.left == null && node.right == null && remain == node.val) {
            result.add(new ArrayList<>(path));
        }
        dfs(node.left, remain - node.val, path, result);
        dfs(node.right, remain - node.val, path, result);
        path.remove(path.size() - 1);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(5, new TreeNode(4, new TreeNode(11, new TreeNode(7), new TreeNode(2)), null),
                new TreeNode(8, new TreeNode(13), new TreeNode(4, new TreeNode(5), new TreeNode(1))));
        System.out.println("Test 1: " + pathSum(t1, 22)); // [[5,4,11,2],[5,8,4,5]]
        System.out.println("Test 2: " + pathSum(null, 0)); // []
    }
}

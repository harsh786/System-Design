/**
 * Problem 10: Binary Tree Maximum Path Sum (LeetCode 124)
 * 
 * Approach: DFS. At each node, max path through it = node.val + max(0,left) + max(0,right).
 * Track global max. Return node.val + max(0, max(left,right)) as contribution to parent.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Finding the most profitable pipeline path through a network of
 * services where each service has a cost/revenue value.
 */
public class Problem10_BinaryTreeMaxPathSum {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static int maxSum;

    public static int maxPathSum(TreeNode root) {
        maxSum = Integer.MIN_VALUE;
        dfs(root);
        return maxSum;
    }

    private static int dfs(TreeNode node) {
        if (node == null) return 0;
        int left = Math.max(0, dfs(node.left));
        int right = Math.max(0, dfs(node.right));
        maxSum = Math.max(maxSum, node.val + left + right);
        return node.val + Math.max(left, right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2), new TreeNode(3));
        System.out.println("Test 1: " + maxPathSum(t1)); // 6

        TreeNode t2 = new TreeNode(-10, new TreeNode(9), new TreeNode(20, new TreeNode(15), new TreeNode(7)));
        System.out.println("Test 2: " + maxPathSum(t2)); // 42

        System.out.println("Test 3 (negative): " + maxPathSum(new TreeNode(-3))); // -3

        TreeNode t4 = new TreeNode(2, new TreeNode(-1), null);
        System.out.println("Test 4: " + maxPathSum(t4)); // 2
    }
}

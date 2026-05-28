/**
 * Problem: Binary Tree Maximum Path Sum (LeetCode 124)
 * Approach: DFS returning max gain from each subtree, updating global max
 * Time: O(N), Space: O(H)
 * Production Analogy: Finding highest-throughput path in a service dependency tree
 */
public class Problem15_BinaryTreeMaxPathSum {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    int maxSum = Integer.MIN_VALUE;

    public int maxPathSum(TreeNode root) {
        maxGain(root);
        return maxSum;
    }

    private int maxGain(TreeNode node) {
        if (node == null) return 0;
        int left = Math.max(0, maxGain(node.left));
        int right = Math.max(0, maxGain(node.right));
        maxSum = Math.max(maxSum, node.val + left + right);
        return node.val + Math.max(left, right);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(-10);
        root.left = new TreeNode(9);
        root.right = new TreeNode(20); root.right.left = new TreeNode(15); root.right.right = new TreeNode(7);
        System.out.println(new Problem15_BinaryTreeMaxPathSum().maxPathSum(root)); // 42
    }
}

/**
 * Problem: Count Complete Tree Nodes (LeetCode 222)
 * Approach: Binary search on last level using height comparison
 * Complexity: O(log^2 n) time, O(log n) space
 * Production Analogy: Efficient resource counting in balanced hierarchical systems
 */
public class Problem32_CountCompleteTreeNodes {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val=v; } }

    public int countNodes(TreeNode root) {
        if (root == null) return 0;
        int leftH = height(root.left), rightH = height(root.right);
        if (leftH == rightH) return (1 << leftH) + countNodes(root.right);
        else return (1 << rightH) + countNodes(root.left);
    }
    int height(TreeNode node) { int h = 0; while (node != null) { h++; node = node.left; } return h; }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.left = new TreeNode(4); root.left.right = new TreeNode(5);
        root.right.left = new TreeNode(6);
        System.out.println(new Problem32_CountCompleteTreeNodes().countNodes(root)); // 6
    }
}

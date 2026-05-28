/**
 * Problem 44: Minimum Absolute Difference in BST (LeetCode 530)
 * 
 * Approach: Inorder traversal gives sorted order. Min diff is between consecutive elements.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Finding the closest two timestamps in a sorted event log for collision detection.
 */
public class Problem44_MinAbsDiffInBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static int minDiff;
    static Integer prev;

    public static int getMinimumDifference(TreeNode root) {
        minDiff = Integer.MAX_VALUE;
        prev = null;
        inorder(root);
        return minDiff;
    }

    private static void inorder(TreeNode node) {
        if (node == null) return;
        inorder(node.left);
        if (prev != null) minDiff = Math.min(minDiff, node.val - prev);
        prev = node.val;
        inorder(node.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(4, new TreeNode(2, new TreeNode(1), new TreeNode(3)), new TreeNode(6));
        System.out.println("Test 1: " + getMinimumDifference(t1)); // 1

        TreeNode t2 = new TreeNode(1, new TreeNode(0), new TreeNode(48, new TreeNode(12), new TreeNode(49)));
        System.out.println("Test 2: " + getMinimumDifference(t2)); // 1
    }
}

/**
 * Problem 12: Balanced Binary Tree (LeetCode 110)
 * 
 * Approach: DFS returning height; return -1 if unbalanced (early termination).
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Checking if a load balancer's routing tree is balanced
 * to ensure even traffic distribution.
 */
public class Problem12_BalancedBinaryTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static boolean isBalanced(TreeNode root) {
        return checkHeight(root) != -1;
    }

    private static int checkHeight(TreeNode node) {
        if (node == null) return 0;
        int left = checkHeight(node.left);
        if (left == -1) return -1;
        int right = checkHeight(node.right);
        if (right == -1) return -1;
        if (Math.abs(left - right) > 1) return -1;
        return 1 + Math.max(left, right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(3, new TreeNode(9), new TreeNode(20, new TreeNode(15), new TreeNode(7)));
        System.out.println("Test 1: " + isBalanced(t1)); // true

        TreeNode t2 = new TreeNode(1, new TreeNode(2, new TreeNode(3, new TreeNode(4), null), null), new TreeNode(2));
        System.out.println("Test 2: " + isBalanced(t2)); // false

        System.out.println("Test 3: " + isBalanced(null)); // true
    }
}

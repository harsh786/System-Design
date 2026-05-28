/**
 * Problem 24: Symmetric Tree (LeetCode 101)
 * 
 * Approach: Check if left subtree mirrors right subtree recursively.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Verifying redundant systems are configured identically (active-active mirrors).
 */
public class Problem24_SymmetricTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static boolean isSymmetric(TreeNode root) {
        if (root == null) return true;
        return isMirror(root.left, root.right);
    }

    private static boolean isMirror(TreeNode a, TreeNode b) {
        if (a == null && b == null) return true;
        if (a == null || b == null) return false;
        return a.val == b.val && isMirror(a.left, b.right) && isMirror(a.right, b.left);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, new TreeNode(3), new TreeNode(4)),
                new TreeNode(2, new TreeNode(4), new TreeNode(3)));
        System.out.println("Test 1: " + isSymmetric(t1)); // true

        TreeNode t2 = new TreeNode(1, new TreeNode(2, null, new TreeNode(3)),
                new TreeNode(2, null, new TreeNode(3)));
        System.out.println("Test 2: " + isSymmetric(t2)); // false

        System.out.println("Test 3: " + isSymmetric(null)); // true
    }
}

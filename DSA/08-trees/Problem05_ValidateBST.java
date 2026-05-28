/**
 * Problem 5: Validate Binary Search Tree (LeetCode 98)
 * 
 * Approach: DFS with min/max bounds. Each node must be within (min, max) range.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Validating that a sorted index (like a B-tree in DB)
 * maintains its invariant after writes.
 */
public class Problem05_ValidateBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static boolean isValidBST(TreeNode root) {
        return validate(root, Long.MIN_VALUE, Long.MAX_VALUE);
    }

    private static boolean validate(TreeNode node, long min, long max) {
        if (node == null) return true;
        if (node.val <= min || node.val >= max) return false;
        return validate(node.left, min, node.val) && validate(node.right, node.val, max);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(2, new TreeNode(1), new TreeNode(3));
        System.out.println("Test 1 (valid): " + isValidBST(t1)); // true

        TreeNode t2 = new TreeNode(5, new TreeNode(1), new TreeNode(4, new TreeNode(3), new TreeNode(6)));
        System.out.println("Test 2 (invalid): " + isValidBST(t2)); // false

        System.out.println("Test 3 (null): " + isValidBST(null)); // true

        // Edge: equal values not allowed
        TreeNode t3 = new TreeNode(1, new TreeNode(1), null);
        System.out.println("Test 4 (equal vals): " + isValidBST(t3)); // false
    }
}

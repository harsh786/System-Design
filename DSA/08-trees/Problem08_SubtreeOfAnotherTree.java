/**
 * Problem 8: Subtree of Another Tree (LeetCode 572)
 * 
 * Approach: For each node in main tree, check if subtree rooted there equals subRoot.
 * Time: O(m*n), Space: O(h)
 * 
 * Production Analogy: Checking if a component template exists within a larger page DOM.
 */
public class Problem08_SubtreeOfAnotherTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static boolean isSubtree(TreeNode root, TreeNode subRoot) {
        if (root == null) return false;
        if (isSame(root, subRoot)) return true;
        return isSubtree(root.left, subRoot) || isSubtree(root.right, subRoot);
    }

    private static boolean isSame(TreeNode a, TreeNode b) {
        if (a == null && b == null) return true;
        if (a == null || b == null) return false;
        return a.val == b.val && isSame(a.left, b.left) && isSame(a.right, b.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(3, new TreeNode(4, new TreeNode(1), new TreeNode(2)), new TreeNode(5));
        TreeNode s1 = new TreeNode(4, new TreeNode(1), new TreeNode(2));
        System.out.println("Test 1: " + isSubtree(t1, s1)); // true

        TreeNode t2 = new TreeNode(3, new TreeNode(4, new TreeNode(1), new TreeNode(2, new TreeNode(0), null)), new TreeNode(5));
        System.out.println("Test 2: " + isSubtree(t2, s1)); // false

        System.out.println("Test 3 (null sub): " + isSubtree(t1, null)); // edge: depends on def
    }
}

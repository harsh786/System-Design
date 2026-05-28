/**
 * Problem 48: Binary Tree Pruning (LeetCode 814)
 * 
 * Approach: Post-order DFS. If subtree contains no 1, prune it (return null).
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Removing inactive feature flag branches from a config tree.
 */
public class Problem48_BinaryTreePruning {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode pruneTree(TreeNode root) {
        if (root == null) return null;
        root.left = pruneTree(root.left);
        root.right = pruneTree(root.right);
        if (root.val == 0 && root.left == null && root.right == null) return null;
        return root;
    }

    static void printPreorder(TreeNode root) {
        if (root == null) return;
        System.out.print(root.val + " ");
        printPreorder(root.left);
        printPreorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, null, new TreeNode(0, new TreeNode(0), new TreeNode(1)));
        t1 = pruneTree(t1);
        System.out.print("Test 1: "); printPreorder(t1); System.out.println(); // 1 0 1

        TreeNode t2 = new TreeNode(1, new TreeNode(0, new TreeNode(0), new TreeNode(0)), new TreeNode(1, new TreeNode(0), new TreeNode(1)));
        t2 = pruneTree(t2);
        System.out.print("Test 2: "); printPreorder(t2); System.out.println(); // 1 1 1

        System.out.println("Test 3: " + pruneTree(new TreeNode(0))); // null
    }
}

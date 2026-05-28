/**
 * Problem 32: Trim a Binary Search Tree (LeetCode 669)
 * 
 * Approach: If node.val < low, return trimmed right subtree. If > high, return trimmed left.
 * Otherwise trim both children.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Pruning expired entries from a time-range index in a database.
 */
public class Problem32_TrimBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode trimBST(TreeNode root, int low, int high) {
        if (root == null) return null;
        if (root.val < low) return trimBST(root.right, low, high);
        if (root.val > high) return trimBST(root.left, low, high);
        root.left = trimBST(root.left, low, high);
        root.right = trimBST(root.right, low, high);
        return root;
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(0), new TreeNode(2));
        t1 = trimBST(t1, 1, 2);
        System.out.print("Test 1: "); printInorder(t1); System.out.println(); // 1 2

        TreeNode t2 = new TreeNode(3, new TreeNode(0, null, new TreeNode(2, new TreeNode(1), null)), new TreeNode(4));
        t2 = trimBST(t2, 1, 3);
        System.out.print("Test 2: "); printInorder(t2); System.out.println(); // 1 2 3
    }
}

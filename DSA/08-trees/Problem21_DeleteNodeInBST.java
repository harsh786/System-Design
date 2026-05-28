/**
 * Problem 21: Delete Node in a BST (LeetCode 450)
 * 
 * Approach: Find node, then: if leaf delete, if one child replace, if two children
 * replace with inorder successor (smallest in right subtree) and delete successor.
 * Time: O(h), Space: O(h)
 * 
 * Production Analogy: Removing an entry from a B-tree index while maintaining sort order.
 */
public class Problem21_DeleteNodeInBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode deleteNode(TreeNode root, int key) {
        if (root == null) return null;
        if (key < root.val) root.left = deleteNode(root.left, key);
        else if (key > root.val) root.right = deleteNode(root.right, key);
        else {
            if (root.left == null) return root.right;
            if (root.right == null) return root.left;
            TreeNode succ = root.right;
            while (succ.left != null) succ = succ.left;
            root.val = succ.val;
            root.right = deleteNode(root.right, succ.val);
        }
        return root;
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(5, new TreeNode(3, new TreeNode(2), new TreeNode(4)),
                new TreeNode(6, null, new TreeNode(7)));
        t1 = deleteNode(t1, 3);
        System.out.print("Test 1 (del 3): "); printInorder(t1); System.out.println(); // 2 4 5 6 7

        t1 = deleteNode(t1, 5);
        System.out.print("Test 2 (del 5): "); printInorder(t1); System.out.println(); // 2 4 6 7

        System.out.println("Test 3 (del from null): " + deleteNode(null, 1)); // null
    }
}

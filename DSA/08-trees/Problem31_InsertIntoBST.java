/**
 * Problem 31: Insert into a Binary Search Tree (LeetCode 701)
 * 
 * Approach: Traverse BST to find null spot, insert new node there.
 * Time: O(h), Space: O(h) recursive
 * 
 * Production Analogy: Adding a new entry to a sorted index while maintaining tree structure.
 */
public class Problem31_InsertIntoBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode insertIntoBST(TreeNode root, int val) {
        if (root == null) return new TreeNode(val);
        if (val < root.val) root.left = insertIntoBST(root.left, val);
        else root.right = insertIntoBST(root.right, val);
        return root;
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(4, new TreeNode(2, new TreeNode(1), new TreeNode(3)), new TreeNode(7));
        t1 = insertIntoBST(t1, 5);
        System.out.print("Test 1: "); printInorder(t1); System.out.println(); // 1 2 3 4 5 7

        TreeNode t2 = insertIntoBST(null, 5);
        System.out.println("Test 2: " + t2.val); // 5
    }
}

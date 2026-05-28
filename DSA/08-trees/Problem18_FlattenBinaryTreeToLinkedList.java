/**
 * Problem 18: Flatten Binary Tree to Linked List (LeetCode 114)
 * 
 * Approach: Reverse postorder (right, left, root). Keep track of prev node.
 * Set current.right = prev, current.left = null.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Flattening a nested menu/navigation tree into a linear list for rendering.
 */
public class Problem18_FlattenBinaryTreeToLinkedList {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static TreeNode prev;

    public static void flatten(TreeNode root) {
        prev = null;
        flattenHelper(root);
    }

    private static void flattenHelper(TreeNode node) {
        if (node == null) return;
        flattenHelper(node.right);
        flattenHelper(node.left);
        node.right = prev;
        node.left = null;
        prev = node;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, new TreeNode(3), new TreeNode(4)), new TreeNode(5, null, new TreeNode(6)));
        flatten(t1);
        System.out.print("Test 1: ");
        TreeNode curr = t1;
        while (curr != null) { System.out.print(curr.val + " "); curr = curr.right; }
        System.out.println(); // 1 2 3 4 5 6

        // Null test
        flatten(null); // no exception
        System.out.println("Test 2: null handled");
    }
}

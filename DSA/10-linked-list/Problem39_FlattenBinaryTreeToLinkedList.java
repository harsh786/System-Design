/**
 * Problem 39: Flatten Binary Tree to Linked List (in-place, preorder)
 * 
 * Approach: Morris-like traversal. For each node with left child, find rightmost
 * of left subtree, connect it to right child, move left to right.
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Serializing a hierarchical org chart into a flat 
 * sequential processing pipeline while preserving visit order.
 */
public class Problem39_FlattenBinaryTreeToLinkedList {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val=v; left=l; right=r; }
    }

    public static void flatten(TreeNode root) {
        TreeNode curr = root;
        while (curr != null) {
            if (curr.left != null) {
                TreeNode rightmost = curr.left;
                while (rightmost.right != null) rightmost = rightmost.right;
                rightmost.right = curr.right;
                curr.right = curr.left;
                curr.left = null;
            }
            curr = curr.right;
        }
    }

    static void printList(TreeNode root) {
        while (root != null) { System.out.print(root.val + "->"); root = root.right; }
        System.out.println("null");
    }

    public static void main(String[] args) {
        //     1
        //    / \
        //   2   5
        //  / \   \
        // 3   4   6
        TreeNode root = new TreeNode(1,
            new TreeNode(2, new TreeNode(3), new TreeNode(4)),
            new TreeNode(5, null, new TreeNode(6)));
        flatten(root);
        printList(root); // 1->2->3->4->5->6->null

        TreeNode single = new TreeNode(0);
        flatten(single);
        printList(single); // 0->null
    }
}

/**
 * Problem 20: Recover Binary Search Tree (LeetCode 99)
 * 
 * Approach: Inorder traversal to find two swapped nodes. First bad pair gives first node,
 * last bad pair gives second node. Swap their values.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Detecting and fixing two corrupted entries in a sorted database index.
 */
public class Problem20_RecoverBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static TreeNode first, second, prev;

    public static void recoverTree(TreeNode root) {
        first = second = prev = null;
        inorder(root);
        int temp = first.val;
        first.val = second.val;
        second.val = temp;
    }

    private static void inorder(TreeNode node) {
        if (node == null) return;
        inorder(node.left);
        if (prev != null && prev.val > node.val) {
            if (first == null) first = prev;
            second = node;
        }
        prev = node;
        inorder(node.right);
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(3, null, new TreeNode(2)), null);
        System.out.print("Before: "); printInorder(t1); System.out.println();
        recoverTree(t1);
        System.out.print("After:  "); printInorder(t1); System.out.println(); // 1 2 3

        TreeNode t2 = new TreeNode(3, new TreeNode(1), new TreeNode(4, new TreeNode(2), null));
        recoverTree(t2);
        System.out.print("Test 2: "); printInorder(t2); System.out.println(); // 1 2 3 4
    }
}

/**
 * Problem: Recover Binary Search Tree (LeetCode 99)
 * Approach: In-order DFS to find two swapped nodes (prev > curr violations)
 * Time: O(N), Space: O(H)
 * Production Analogy: Detecting and fixing ordering violations in sorted indexes
 */
public class Problem42_RecoverBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    TreeNode first, second, prev;

    public void recoverTree(TreeNode root) {
        inorder(root);
        int tmp = first.val; first.val = second.val; second.val = tmp;
    }

    private void inorder(TreeNode node) {
        if (node == null) return;
        inorder(node.left);
        if (prev != null && prev.val > node.val) {
            if (first == null) first = prev;
            second = node;
        }
        prev = node;
        inorder(node.right);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(1); root.right = new TreeNode(4);
        root.right.left = new TreeNode(2); // 3 and 2 are swapped
        new Problem42_RecoverBST().recoverTree(root);
        System.out.println("Root: " + root.val); // should fix the tree
    }
}

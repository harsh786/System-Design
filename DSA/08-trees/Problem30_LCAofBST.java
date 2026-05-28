/**
 * Problem 30: Lowest Common Ancestor of a BST (LeetCode 235)
 * 
 * Approach: Exploit BST property. If both p,q < node, go left. Both > node, go right. Else current is LCA.
 * Time: O(h), Space: O(1) iterative
 * 
 * Production Analogy: Finding the common routing prefix in a hierarchical IP address tree.
 */
public class Problem30_LCAofBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode lowestCommonAncestor(TreeNode root, TreeNode p, TreeNode q) {
        while (root != null) {
            if (p.val < root.val && q.val < root.val) root = root.left;
            else if (p.val > root.val && q.val > root.val) root = root.right;
            else return root;
        }
        return null;
    }

    public static void main(String[] args) {
        TreeNode n2 = new TreeNode(2);
        TreeNode n4 = new TreeNode(4);
        TreeNode n8 = new TreeNode(8);
        TreeNode root = new TreeNode(6, new TreeNode(2, new TreeNode(0), new TreeNode(4, new TreeNode(3), new TreeNode(5))),
                new TreeNode(8, new TreeNode(7), new TreeNode(9)));
        System.out.println("LCA(2,8): " + lowestCommonAncestor(root, n2, n8).val); // 6
        System.out.println("LCA(2,4): " + lowestCommonAncestor(root, n2, n4).val); // 2
    }
}

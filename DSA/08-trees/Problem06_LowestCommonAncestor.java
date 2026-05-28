/**
 * Problem 6: Lowest Common Ancestor of a Binary Tree (LeetCode 236)
 * 
 * Approach: DFS - if current node is p or q, return it. If left and right both
 * return non-null, current node is LCA. Otherwise return whichever is non-null.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Finding the common parent service in a microservice call graph
 * that both failing services depend on for root cause analysis.
 */
public class Problem06_LowestCommonAncestor {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode lowestCommonAncestor(TreeNode root, TreeNode p, TreeNode q) {
        if (root == null || root == p || root == q) return root;
        TreeNode left = lowestCommonAncestor(root.left, p, q);
        TreeNode right = lowestCommonAncestor(root.right, p, q);
        if (left != null && right != null) return root;
        return left != null ? left : right;
    }

    public static void main(String[] args) {
        TreeNode n5 = new TreeNode(5);
        TreeNode n1 = new TreeNode(1);
        TreeNode n3 = new TreeNode(3, n5, n1);
        TreeNode n8 = new TreeNode(8);
        TreeNode n4 = new TreeNode(4);
        TreeNode root = new TreeNode(3, n3, new TreeNode(7, n8, n4));
        // Note: reusing value 3 for demo; using references
        
        System.out.println("LCA of 5,1: " + lowestCommonAncestor(n3, n5, n1).val); // 3 (n3)
        System.out.println("LCA of 5,4: " + lowestCommonAncestor(root, n5, n4).val); // 3 (root)
    }
}

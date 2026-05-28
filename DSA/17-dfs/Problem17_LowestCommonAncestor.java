/**
 * Problem: Lowest Common Ancestor (LeetCode 236)
 * Approach: DFS - if current node matches p or q, return it; otherwise check both subtrees
 * Time: O(N), Space: O(H)
 * Production Analogy: Finding common parent service in a microservice dependency tree for shared config
 */
public class Problem17_LowestCommonAncestor {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public TreeNode lowestCommonAncestor(TreeNode root, TreeNode p, TreeNode q) {
        if (root == null || root == p || root == q) return root;
        TreeNode left = lowestCommonAncestor(root.left, p, q);
        TreeNode right = lowestCommonAncestor(root.right, p, q);
        if (left != null && right != null) return root;
        return left != null ? left : right;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3);
        root.left = new TreeNode(5); root.right = new TreeNode(1);
        root.left.left = new TreeNode(6); root.left.right = new TreeNode(2);
        TreeNode lca = new Problem17_LowestCommonAncestor().lowestCommonAncestor(root, root.left, root.left.right);
        System.out.println("LCA: " + lca.val); // 5
    }
}

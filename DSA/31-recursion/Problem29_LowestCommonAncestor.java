public class Problem29_LowestCommonAncestor {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static TreeNode lowestCommonAncestor(TreeNode root, TreeNode p, TreeNode q) {
        if (root == null || root == p || root == q) return root;
        TreeNode left = lowestCommonAncestor(root.left, p, q);
        TreeNode right = lowestCommonAncestor(root.right, p, q);
        if (left != null && right != null) return root;
        return left != null ? left : right;
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(5); root.right = new TreeNode(1);
        root.left.left = new TreeNode(6); root.left.right = new TreeNode(2);
        System.out.println(lowestCommonAncestor(root, root.left, root.right).val); // 3
        System.out.println(lowestCommonAncestor(root, root.left, root.left.right).val); // 5
    }
}

public class Problem14_InvertBinaryTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static TreeNode invertTree(TreeNode root) {
        if (root == null) return null;
        TreeNode tmp = root.left;
        root.left = invertTree(root.right);
        root.right = invertTree(tmp);
        return root;
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(4); root.left = new TreeNode(2); root.right = new TreeNode(7);
        TreeNode res = invertTree(root);
        System.out.println(res.left.val + " " + res.right.val); // 7 2
    }
}

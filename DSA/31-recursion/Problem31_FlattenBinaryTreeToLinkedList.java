public class Problem31_FlattenBinaryTreeToLinkedList {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static TreeNode prev = null;
    public static void flatten(TreeNode root) {
        if (root == null) return;
        flatten(root.right);
        flatten(root.left);
        root.right = prev; root.left = null;
        prev = root;
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(2); root.right = new TreeNode(5);
        root.left.left = new TreeNode(3); root.left.right = new TreeNode(4); root.right.right = new TreeNode(6);
        prev = null; flatten(root);
        while (root != null) { System.out.print(root.val + " "); root = root.right; }
    }
}

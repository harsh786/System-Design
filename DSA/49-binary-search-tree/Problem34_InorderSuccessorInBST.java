public class Problem34_InorderSuccessorInBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static TreeNode inorderSuccessor(TreeNode root, TreeNode p) {
        TreeNode succ = null;
        while (root != null) {
            if (p.val < root.val) { succ = root; root = root.left; }
            else root = root.right;
        }
        return succ;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(5);
        root.left = new TreeNode(3); root.right = new TreeNode(6);
        root.left.left = new TreeNode(2); root.left.right = new TreeNode(4);
        root.left.left.left = new TreeNode(1);
        TreeNode res = inorderSuccessor(root, root.left.right);
        System.out.println(res != null ? res.val : "null"); // 5
    }
}

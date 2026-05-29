public class Problem35_InorderPredecessorInBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static TreeNode inorderPredecessor(TreeNode root, TreeNode p) {
        TreeNode pred = null;
        while (root != null) {
            if (p.val > root.val) { pred = root; root = root.right; }
            else root = root.left;
        }
        return pred;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(5);
        root.left = new TreeNode(3); root.right = new TreeNode(6);
        root.left.left = new TreeNode(2); root.left.right = new TreeNode(4);
        TreeNode res = inorderPredecessor(root, root);
        System.out.println(res != null ? res.val : "null"); // 4
    }
}

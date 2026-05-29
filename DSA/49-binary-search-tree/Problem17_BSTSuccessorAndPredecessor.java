public class Problem17_BSTSuccessorAndPredecessor {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static TreeNode inorderSuccessor(TreeNode root, TreeNode p) {
        TreeNode succ = null;
        while (root != null) {
            if (p.val < root.val) { succ = root; root = root.left; }
            else root = root.right;
        }
        return succ;
    }

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
        root.left = new TreeNode(3); root.right = new TreeNode(7);
        root.left.left = new TreeNode(2); root.left.right = new TreeNode(4);
        root.right.left = new TreeNode(6); root.right.right = new TreeNode(8);
        System.out.println(inorderSuccessor(root, root.left).val); // 4
        System.out.println(inorderPredecessor(root, root.right).val); // 6
    }
}

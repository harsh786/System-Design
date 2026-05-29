public class Problem16_SplitBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    // Split BST into two: one with values <= target, other with values > target
    public static TreeNode[] splitBST(TreeNode root, int target) {
        if (root == null) return new TreeNode[]{null, null};
        if (root.val <= target) {
            TreeNode[] split = splitBST(root.right, target);
            root.right = split[0];
            return new TreeNode[]{root, split[1]};
        } else {
            TreeNode[] split = splitBST(root.left, target);
            root.left = split[1];
            return new TreeNode[]{split[0], root};
        }
    }

    static void inorder(TreeNode n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(4);
        root.left = new TreeNode(2); root.right = new TreeNode(6);
        root.left.left = new TreeNode(1); root.left.right = new TreeNode(3);
        root.right.left = new TreeNode(5); root.right.right = new TreeNode(7);
        TreeNode[] res = splitBST(root, 2);
        inorder(res[0]); System.out.println(); // 1 2
        inorder(res[1]); System.out.println(); // 3 4 5 6 7
    }
}

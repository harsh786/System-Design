public class Problem10_TrimBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static TreeNode trimBST(TreeNode root, int low, int high) {
        if (root == null) return null;
        if (root.val < low) return trimBST(root.right, low, high);
        if (root.val > high) return trimBST(root.left, low, high);
        root.left = trimBST(root.left, low, high);
        root.right = trimBST(root.right, low, high);
        return root;
    }

    static void inorder(TreeNode n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3);
        root.left = new TreeNode(0); root.right = new TreeNode(4);
        root.left.right = new TreeNode(2); root.left.right.left = new TreeNode(1);
        root = trimBST(root, 1, 3);
        inorder(root); System.out.println(); // 1 2 3
    }
}

public class Problem24_IncreasingOrderSearchTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static TreeNode cur;

    public static TreeNode increasingBST(TreeNode root) {
        TreeNode dummy = new TreeNode(0);
        cur = dummy;
        inorder(root);
        return dummy.right;
    }

    private static void inorder(TreeNode n) {
        if (n == null) return;
        inorder(n.left);
        n.left = null;
        cur.right = n;
        cur = n;
        inorder(n.right);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(5);
        root.left = new TreeNode(3); root.right = new TreeNode(6);
        root.left.left = new TreeNode(2); root.left.right = new TreeNode(4);
        root.right.right = new TreeNode(8);
        TreeNode res = increasingBST(root);
        while (res != null) { System.out.print(res.val + " "); res = res.right; }
        System.out.println(); // 2 3 4 5 6 8
    }
}

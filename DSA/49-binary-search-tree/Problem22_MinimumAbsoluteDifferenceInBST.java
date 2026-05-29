public class Problem22_MinimumAbsoluteDifferenceInBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static int min, prev2;

    public static int getMinimumDifference(TreeNode root) {
        min = Integer.MAX_VALUE; prev2 = -1;
        inorder(root);
        return min;
    }

    private static void inorder(TreeNode n) {
        if (n == null) return;
        inorder(n.left);
        if (prev2 >= 0) min = Math.min(min, n.val - prev2);
        prev2 = n.val;
        inorder(n.right);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(4);
        root.left = new TreeNode(2); root.right = new TreeNode(6);
        root.left.left = new TreeNode(1); root.left.right = new TreeNode(3);
        System.out.println(getMinimumDifference(root)); // 1
    }
}

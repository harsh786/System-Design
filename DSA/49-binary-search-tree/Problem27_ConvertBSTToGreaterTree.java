public class Problem27_ConvertBSTToGreaterTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static int sum;

    public static TreeNode convertBST(TreeNode root) {
        sum = 0;
        reverseInorder(root);
        return root;
    }

    private static void reverseInorder(TreeNode n) {
        if (n == null) return;
        reverseInorder(n.right);
        sum += n.val;
        n.val = sum;
        reverseInorder(n.left);
    }

    static void inorder(TreeNode n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(4);
        root.left = new TreeNode(1); root.right = new TreeNode(6);
        root.left.left = new TreeNode(0); root.left.right = new TreeNode(2);
        root.right.left = new TreeNode(5); root.right.right = new TreeNode(7);
        convertBST(root);
        inorder(root); System.out.println(); // 25 22 18 15 11 6 7 -> with proper sums
    }
}

public class Problem20_BSTFromPreorder {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    static int idx;

    public static TreeNode bstFromPreorder(int[] preorder) {
        idx = 0;
        return build(preorder, Integer.MAX_VALUE);
    }

    private static TreeNode build(int[] preorder, int bound) {
        if (idx >= preorder.length || preorder[idx] > bound) return null;
        TreeNode node = new TreeNode(preorder[idx++]);
        node.left = build(preorder, node.val);
        node.right = build(preorder, bound);
        return node;
    }

    static void inorder(TreeNode n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        TreeNode root = bstFromPreorder(new int[]{8, 5, 1, 7, 10, 12});
        inorder(root); System.out.println(); // 1 5 7 8 10 12
    }
}

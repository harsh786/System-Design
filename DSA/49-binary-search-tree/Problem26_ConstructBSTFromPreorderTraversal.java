public class Problem26_ConstructBSTFromPreorderTraversal {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static TreeNode bstFromPreorder(int[] preorder) {
        return build(preorder, 0, preorder.length - 1);
    }

    private static TreeNode build(int[] pre, int lo, int hi) {
        if (lo > hi) return null;
        TreeNode node = new TreeNode(pre[lo]);
        int idx = lo + 1;
        while (idx <= hi && pre[idx] < pre[lo]) idx++;
        node.left = build(pre, lo + 1, idx - 1);
        node.right = build(pre, idx, hi);
        return node;
    }

    static void inorder(TreeNode n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        TreeNode root = bstFromPreorder(new int[]{8,5,1,7,10,12});
        inorder(root); System.out.println(); // 1 5 7 8 10 12
    }
}

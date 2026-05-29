public class Problem32_CountCompleteTreeNodes {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static int countNodes(TreeNode root) {
        if (root == null) return 0;
        int lh = 0, rh = 0;
        TreeNode l = root, r = root;
        while (l != null) { lh++; l = l.left; }
        while (r != null) { rh++; r = r.right; }
        if (lh == rh) return (1 << lh) - 1;
        return 1 + countNodes(root.left) + countNodes(root.right);
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.left = new TreeNode(4); root.left.right = new TreeNode(5); root.right.left = new TreeNode(6);
        System.out.println(countNodes(root)); // 6
    }
}

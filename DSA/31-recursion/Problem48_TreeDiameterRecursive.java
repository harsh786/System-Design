public class Problem48_TreeDiameterRecursive {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static int diameter;
    public static int diameterOfBinaryTree(TreeNode root) {
        diameter = 0;
        depth(root);
        return diameter;
    }
    static int depth(TreeNode node) {
        if (node == null) return 0;
        int left = depth(node.left), right = depth(node.right);
        diameter = Math.max(diameter, left + right);
        return 1 + Math.max(left, right);
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.left = new TreeNode(4); root.left.right = new TreeNode(5);
        System.out.println(diameterOfBinaryTree(root)); // 3
    }
}

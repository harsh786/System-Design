public class Problem28_BinaryTreeMaximumPathSum {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static int maxSum;
    public static int maxPathSum(TreeNode root) {
        maxSum = Integer.MIN_VALUE;
        dfs(root);
        return maxSum;
    }
    static int dfs(TreeNode node) {
        if (node == null) return 0;
        int left = Math.max(0, dfs(node.left));
        int right = Math.max(0, dfs(node.right));
        maxSum = Math.max(maxSum, left + right + node.val);
        return Math.max(left, right) + node.val;
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(-10); root.left = new TreeNode(9); root.right = new TreeNode(20);
        root.right.left = new TreeNode(15); root.right.right = new TreeNode(7);
        System.out.println(maxPathSum(root)); // 42
    }
}

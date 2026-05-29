public class Problem26_PathSum {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static boolean hasPathSum(TreeNode root, int targetSum) {
        if (root == null) return false;
        if (root.left == null && root.right == null) return root.val == targetSum;
        return hasPathSum(root.left, targetSum - root.val) || hasPathSum(root.right, targetSum - root.val);
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(5); root.left = new TreeNode(4); root.right = new TreeNode(8);
        root.left.left = new TreeNode(11); root.left.left.left = new TreeNode(7); root.left.left.right = new TreeNode(2);
        System.out.println(hasPathSum(root, 22)); // true
    }
}

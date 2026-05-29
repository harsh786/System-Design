public class Problem29_MaximumSumBSTInBinaryTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static int maxSum;

    public static int maxSumBST(TreeNode root) {
        maxSum = 0;
        dfs(root);
        return maxSum;
    }

    // returns [isBST(0/1), min, max, sum]
    private static int[] dfs(TreeNode node) {
        if (node == null) return new int[]{1, Integer.MAX_VALUE, Integer.MIN_VALUE, 0};
        int[] left = dfs(node.left), right = dfs(node.right);
        if (left[0] == 1 && right[0] == 1 && node.val > left[2] && node.val < right[1]) {
            int sum = left[3] + right[3] + node.val;
            maxSum = Math.max(maxSum, sum);
            return new int[]{1, Math.min(node.val, left[1]), Math.max(node.val, right[2]), sum};
        }
        return new int[]{0, 0, 0, 0};
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(4); root.right = new TreeNode(3);
        root.left.left = new TreeNode(2); root.left.right = new TreeNode(4);
        root.right.left = new TreeNode(2); root.right.right = new TreeNode(5);
        root.right.right.left = new TreeNode(4); root.right.right.right = new TreeNode(6);
        System.out.println(maxSumBST(root)); // 20
    }
}

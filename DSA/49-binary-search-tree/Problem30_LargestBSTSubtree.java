public class Problem30_LargestBSTSubtree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    static int maxSize;

    public static int largestBSTSubtree(TreeNode root) {
        maxSize = 0;
        dfs(root);
        return maxSize;
    }

    // returns [size, min, max] or null if not BST
    private static int[] dfs(TreeNode node) {
        if (node == null) return new int[]{0, Integer.MAX_VALUE, Integer.MIN_VALUE};
        int[] left = dfs(node.left), right = dfs(node.right);
        if (left != null && right != null && node.val > left[2] && node.val < right[1]) {
            int size = left[0] + right[0] + 1;
            maxSize = Math.max(maxSize, size);
            return new int[]{size, Math.min(node.val, left[1]), Math.max(node.val, right[2])};
        }
        return null;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(10);
        root.left = new TreeNode(5); root.right = new TreeNode(15);
        root.left.left = new TreeNode(1); root.left.right = new TreeNode(8);
        root.right.right = new TreeNode(7);
        System.out.println(largestBSTSubtree(root)); // 3
    }
}

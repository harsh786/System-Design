/**
 * Problem: House Robber III (LeetCode 337)
 * Approach: DFS returning [rob_this_node, skip_this_node] pair
 * Time: O(N), Space: O(H)
 * Production Analogy: Optimal resource allocation in hierarchical org avoiding adjacent-level conflicts
 */
public class Problem43_HouseRobberIII {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public int rob(TreeNode root) {
        int[] res = dfs(root);
        return Math.max(res[0], res[1]);
    }

    private int[] dfs(TreeNode node) {
        if (node == null) return new int[]{0, 0};
        int[] left = dfs(node.left), right = dfs(node.right);
        int rob = node.val + left[1] + right[1];
        int skip = Math.max(left[0], left[1]) + Math.max(right[0], right[1]);
        return new int[]{rob, skip};
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3);
        root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.right = new TreeNode(3); root.right.right = new TreeNode(1);
        System.out.println(new Problem43_HouseRobberIII().rob(root)); // 7
    }
}

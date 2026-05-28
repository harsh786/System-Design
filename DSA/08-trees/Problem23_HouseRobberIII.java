/**
 * Problem 23: House Robber III (LeetCode 337)
 * 
 * Approach: DFS returning pair [rob_this_node, skip_this_node].
 * rob = node.val + skip_left + skip_right
 * skip = max(rob_left, skip_left) + max(rob_right, skip_right)
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Selecting non-adjacent cache layers to invalidate for max freed memory.
 */
public class Problem23_HouseRobberIII {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int rob(TreeNode root) {
        int[] res = dfs(root);
        return Math.max(res[0], res[1]);
    }

    private static int[] dfs(TreeNode node) {
        if (node == null) return new int[]{0, 0};
        int[] left = dfs(node.left);
        int[] right = dfs(node.right);
        int robThis = node.val + left[1] + right[1];
        int skipThis = Math.max(left[0], left[1]) + Math.max(right[0], right[1]);
        return new int[]{robThis, skipThis};
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(3, new TreeNode(2, null, new TreeNode(3)), new TreeNode(3, null, new TreeNode(1)));
        System.out.println("Test 1: " + rob(t1)); // 7

        TreeNode t2 = new TreeNode(3, new TreeNode(4, new TreeNode(1), new TreeNode(3)), new TreeNode(5, null, new TreeNode(1)));
        System.out.println("Test 2: " + rob(t2)); // 9

        System.out.println("Test 3: " + rob(null)); // 0
    }
}

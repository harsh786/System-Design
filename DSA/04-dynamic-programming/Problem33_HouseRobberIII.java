/**
 * Problem 33: House Robber III (Tree-shaped houses)
 * 
 * Houses form a binary tree. Cannot rob directly-linked parent-child.
 * 
 * For each node return [rob_this, skip_this]:
 * rob_this = node.val + skip_left + skip_right
 * skip_this = max(rob_left, skip_left) + max(rob_right, skip_right)
 * 
 * Time: O(n), Space: O(h) for recursion
 */
public class Problem33_HouseRobberIII {

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
        System.out.println("=== House Robber III ===");
        // Tree: [3,2,3,null,3,null,1]
        TreeNode root = new TreeNode(3,
            new TreeNode(2, null, new TreeNode(3)),
            new TreeNode(3, null, new TreeNode(1)));
        System.out.println(rob(root)); // 7

        // Tree: [3,4,5,1,3,null,1]
        TreeNode root2 = new TreeNode(3,
            new TreeNode(4, new TreeNode(1), new TreeNode(3)),
            new TreeNode(5, null, new TreeNode(1)));
        System.out.println(rob(root2)); // 9
    }
}

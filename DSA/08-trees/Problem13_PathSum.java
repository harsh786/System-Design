/**
 * Problem 13: Path Sum (LeetCode 112)
 * 
 * Approach: DFS subtracting node value from target. At leaf, check if remainder is 0.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Checking if any route through a network meets an exact latency budget.
 */
public class Problem13_PathSum {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static boolean hasPathSum(TreeNode root, int targetSum) {
        if (root == null) return false;
        if (root.left == null && root.right == null) return root.val == targetSum;
        return hasPathSum(root.left, targetSum - root.val) || hasPathSum(root.right, targetSum - root.val);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(5, new TreeNode(4, new TreeNode(11, new TreeNode(7), new TreeNode(2)), null),
                new TreeNode(8, new TreeNode(13), new TreeNode(4, null, new TreeNode(1))));
        System.out.println("Test 1: " + hasPathSum(t1, 22)); // true
        System.out.println("Test 2: " + hasPathSum(t1, 50)); // false
        System.out.println("Test 3: " + hasPathSum(null, 0)); // false
        System.out.println("Test 4: " + hasPathSum(new TreeNode(1), 1)); // true
    }
}

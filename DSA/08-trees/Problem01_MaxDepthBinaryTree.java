/**
 * Problem 1: Maximum Depth of Binary Tree (LeetCode 104)
 * 
 * Approach: DFS recursion - depth of a node = 1 + max(depth(left), depth(right))
 * Time: O(n), Space: O(h) where h is height (O(n) worst case skewed tree)
 * 
 * Production Analogy: Like measuring the deepest level of a nested JSON config
 * to determine max recursion depth needed for parsing.
 */
public class Problem01_MaxDepthBinaryTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int maxDepth(TreeNode root) {
        if (root == null) return 0;
        return 1 + Math.max(maxDepth(root.left), maxDepth(root.right));
    }

    public static void main(String[] args) {
        // Test 1: [3,9,20,null,null,15,7] -> 3
        TreeNode t1 = new TreeNode(3, new TreeNode(9), new TreeNode(20, new TreeNode(15), new TreeNode(7)));
        System.out.println("Test 1: " + maxDepth(t1)); // 3

        // Test 2: null -> 0
        System.out.println("Test 2: " + maxDepth(null)); // 0

        // Test 3: single node -> 1
        System.out.println("Test 3: " + maxDepth(new TreeNode(1))); // 1

        // Test 4: skewed tree
        TreeNode t4 = new TreeNode(1, new TreeNode(2, new TreeNode(3), null), null);
        System.out.println("Test 4: " + maxDepth(t4)); // 3
    }
}

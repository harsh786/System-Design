/**
 * Problem 33: Range Sum of BST (LeetCode 938)
 * 
 * Approach: DFS with pruning - skip left if node.val <= low, skip right if node.val >= high.
 * Time: O(n) worst, O(k + log n) best where k = nodes in range, Space: O(h)
 * 
 * Production Analogy: Summing metrics values within a time range from a sorted time-series index.
 */
public class Problem33_RangeSumBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int rangeSumBST(TreeNode root, int low, int high) {
        if (root == null) return 0;
        if (root.val < low) return rangeSumBST(root.right, low, high);
        if (root.val > high) return rangeSumBST(root.left, low, high);
        return root.val + rangeSumBST(root.left, low, high) + rangeSumBST(root.right, low, high);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(10, new TreeNode(5, new TreeNode(3), new TreeNode(7)),
                new TreeNode(15, null, new TreeNode(18)));
        System.out.println("Test 1: " + rangeSumBST(t1, 7, 15)); // 32
        System.out.println("Test 2: " + rangeSumBST(t1, 6, 10)); // 17 (7+10)
        System.out.println("Test 3: " + rangeSumBST(null, 1, 5)); // 0
    }
}

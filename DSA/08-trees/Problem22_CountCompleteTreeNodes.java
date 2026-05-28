/**
 * Problem 22: Count Complete Tree Nodes (LeetCode 222)
 * 
 * Approach: Compare left and right heights. If equal, left subtree is perfect (2^h - 1 + 1 nodes).
 * Otherwise recurse on both sides.
 * Time: O(log^2 n), Space: O(log n)
 * 
 * Production Analogy: Efficiently counting entries in a nearly-full B-tree without scanning all leaves.
 */
public class Problem22_CountCompleteTreeNodes {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int countNodes(TreeNode root) {
        if (root == null) return 0;
        int leftH = 0, rightH = 0;
        TreeNode l = root, r = root;
        while (l != null) { leftH++; l = l.left; }
        while (r != null) { rightH++; r = r.right; }
        if (leftH == rightH) return (1 << leftH) - 1;
        return 1 + countNodes(root.left) + countNodes(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)),
                new TreeNode(3, new TreeNode(6), null));
        System.out.println("Test 1: " + countNodes(t1)); // 6
        System.out.println("Test 2: " + countNodes(null)); // 0
        System.out.println("Test 3: " + countNodes(new TreeNode(1))); // 1
    }
}

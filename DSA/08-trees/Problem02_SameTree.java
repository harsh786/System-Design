/**
 * Problem 2: Same Tree (LeetCode 100)
 * 
 * Approach: Simultaneous DFS on both trees, compare node by node.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Comparing two config file ASTs to detect drift between environments.
 */
public class Problem02_SameTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static boolean isSameTree(TreeNode p, TreeNode q) {
        if (p == null && q == null) return true;
        if (p == null || q == null) return false;
        return p.val == q.val && isSameTree(p.left, q.left) && isSameTree(p.right, q.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2), new TreeNode(3));
        TreeNode t2 = new TreeNode(1, new TreeNode(2), new TreeNode(3));
        System.out.println("Test 1 (same): " + isSameTree(t1, t2)); // true

        TreeNode t3 = new TreeNode(1, new TreeNode(2), null);
        TreeNode t4 = new TreeNode(1, null, new TreeNode(2));
        System.out.println("Test 2 (diff structure): " + isSameTree(t3, t4)); // false

        System.out.println("Test 3 (both null): " + isSameTree(null, null)); // true
        System.out.println("Test 4 (one null): " + isSameTree(t1, null)); // false
    }
}

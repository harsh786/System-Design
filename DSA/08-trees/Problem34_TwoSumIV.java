import java.util.*;
/**
 * Problem 34: Two Sum IV - Input is a BST (LeetCode 653)
 * 
 * Approach: Inorder traversal to get sorted array, then two pointers.
 * Or use HashSet during DFS.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding two transactions in a sorted ledger that sum to a specific amount.
 */
public class Problem34_TwoSumIV {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static boolean findTarget(TreeNode root, int k) {
        Set<Integer> set = new HashSet<>();
        return dfs(root, k, set);
    }

    private static boolean dfs(TreeNode node, int k, Set<Integer> set) {
        if (node == null) return false;
        if (set.contains(k - node.val)) return true;
        set.add(node.val);
        return dfs(node.left, k, set) || dfs(node.right, k, set);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(5, new TreeNode(3, new TreeNode(2), new TreeNode(4)), new TreeNode(6, null, new TreeNode(7)));
        System.out.println("Test 1 (k=9): " + findTarget(t1, 9)); // true (2+7)
        System.out.println("Test 2 (k=28): " + findTarget(t1, 28)); // false
        System.out.println("Test 3: " + findTarget(null, 0)); // false
    }
}

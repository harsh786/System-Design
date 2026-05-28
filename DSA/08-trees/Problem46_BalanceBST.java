import java.util.*;
/**
 * Problem 46: Balance a Binary Search Tree (LeetCode 1382)
 * 
 * Approach: Inorder traversal to get sorted list, then build balanced BST from sorted array.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Rebalancing a degraded database index after many insertions/deletions.
 */
public class Problem46_BalanceBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode balanceBST(TreeNode root) {
        List<Integer> sorted = new ArrayList<>();
        inorder(root, sorted);
        return build(sorted, 0, sorted.size() - 1);
    }

    private static void inorder(TreeNode node, List<Integer> list) {
        if (node == null) return;
        inorder(node.left, list);
        list.add(node.val);
        inorder(node.right, list);
    }

    private static TreeNode build(List<Integer> list, int l, int r) {
        if (l > r) return null;
        int mid = l + (r - l) / 2;
        TreeNode node = new TreeNode(list.get(mid));
        node.left = build(list, l, mid - 1);
        node.right = build(list, mid + 1, r);
        return node;
    }

    static int height(TreeNode node) {
        if (node == null) return 0;
        return 1 + Math.max(height(node.left), height(node.right));
    }

    public static void main(String[] args) {
        // Skewed BST: 1->2->3->4
        TreeNode skewed = new TreeNode(1, null, new TreeNode(2, null, new TreeNode(3, null, new TreeNode(4))));
        System.out.println("Before height: " + height(skewed)); // 4
        TreeNode balanced = balanceBST(skewed);
        System.out.println("After height: " + height(balanced)); // 3
    }
}

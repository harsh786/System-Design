import java.util.*;
/**
 * Problem 28: Boundary of Binary Tree (LeetCode 545)
 * 
 * Approach: Three parts: left boundary (top-down), leaves (left-right), right boundary (bottom-up).
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Tracing the perimeter nodes of a network topology for firewall rules.
 */
public class Problem28_BoundaryOfBinaryTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<Integer> boundaryOfBinaryTree(TreeNode root) {
        List<Integer> result = new ArrayList<>();
        if (root == null) return result;
        result.add(root.val);
        leftBoundary(root.left, result);
        leaves(root.left, result);
        leaves(root.right, result);
        rightBoundary(root.right, result);
        return result;
    }

    private static void leftBoundary(TreeNode node, List<Integer> res) {
        if (node == null || (node.left == null && node.right == null)) return;
        res.add(node.val);
        if (node.left != null) leftBoundary(node.left, res);
        else leftBoundary(node.right, res);
    }

    private static void rightBoundary(TreeNode node, List<Integer> res) {
        if (node == null || (node.left == null && node.right == null)) return;
        if (node.right != null) rightBoundary(node.right, res);
        else rightBoundary(node.left, res);
        res.add(node.val); // bottom-up
    }

    private static void leaves(TreeNode node, List<Integer> res) {
        if (node == null) return;
        if (node.left == null && node.right == null) { res.add(node.val); return; }
        leaves(node.left, res);
        leaves(node.right, res);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, null, new TreeNode(2, new TreeNode(3), new TreeNode(4)));
        System.out.println("Test 1: " + boundaryOfBinaryTree(t1)); // [1,3,4,2]

        TreeNode t2 = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5, new TreeNode(7), new TreeNode(8))),
                new TreeNode(3, new TreeNode(6, new TreeNode(9), new TreeNode(10)), null));
        System.out.println("Test 2: " + boundaryOfBinaryTree(t2)); // [1,2,4,7,8,9,10,6,3]

        System.out.println("Test 3: " + boundaryOfBinaryTree(new TreeNode(1))); // [1]
    }
}

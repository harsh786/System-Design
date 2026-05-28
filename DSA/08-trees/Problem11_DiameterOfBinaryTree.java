/**
 * Problem 11: Diameter of Binary Tree (LeetCode 543)
 * 
 * Approach: DFS returning height. Diameter at each node = leftHeight + rightHeight.
 * Track global max.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Finding the longest request chain in a service mesh topology.
 */
public class Problem11_DiameterOfBinaryTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static int diameter;

    public static int diameterOfBinaryTree(TreeNode root) {
        diameter = 0;
        height(root);
        return diameter;
    }

    private static int height(TreeNode node) {
        if (node == null) return 0;
        int left = height(node.left);
        int right = height(node.right);
        diameter = Math.max(diameter, left + right);
        return 1 + Math.max(left, right);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)), new TreeNode(3));
        System.out.println("Test 1: " + diameterOfBinaryTree(t1)); // 3

        System.out.println("Test 2: " + diameterOfBinaryTree(new TreeNode(1, new TreeNode(2), null))); // 1
        System.out.println("Test 3: " + diameterOfBinaryTree(new TreeNode(1))); // 0
    }
}

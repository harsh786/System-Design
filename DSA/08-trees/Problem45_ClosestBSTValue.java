/**
 * Problem 45: Closest Binary Search Tree Value (LeetCode 270)
 * 
 * Approach: Binary search through BST, tracking closest value seen.
 * Time: O(h), Space: O(1)
 * 
 * Production Analogy: Finding the nearest available time slot in a sorted schedule tree.
 */
public class Problem45_ClosestBSTValue {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int closestValue(TreeNode root, double target) {
        int closest = root.val;
        while (root != null) {
            if (Math.abs(root.val - target) < Math.abs(closest - target)) closest = root.val;
            root = target < root.val ? root.left : root.right;
        }
        return closest;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(4, new TreeNode(2, new TreeNode(1), new TreeNode(3)), new TreeNode(5));
        System.out.println("Test 1 (target=3.7): " + closestValue(t1, 3.7)); // 4
        System.out.println("Test 2 (target=2.1): " + closestValue(t1, 2.1)); // 2
        System.out.println("Test 3 (target=5.0): " + closestValue(t1, 5.0)); // 5
    }
}

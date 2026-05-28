import java.util.*;
/**
 * Problem 49: Even Odd Tree (LeetCode 1609)
 * 
 * Approach: BFS level order. Even levels: values must be odd and strictly increasing.
 * Odd levels: values must be even and strictly decreasing.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Validating alternating constraints on hierarchical data
 * (e.g., alternating security levels in an org chart).
 */
public class Problem49_EvenOddTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static boolean isEvenOddTree(TreeNode root) {
        Queue<TreeNode> queue = new LinkedList<>();
        queue.offer(root);
        int level = 0;
        while (!queue.isEmpty()) {
            int size = queue.size();
            int prev = level % 2 == 0 ? Integer.MIN_VALUE : Integer.MAX_VALUE;
            for (int i = 0; i < size; i++) {
                TreeNode node = queue.poll();
                if (level % 2 == 0) {
                    if (node.val % 2 == 0 || node.val <= prev) return false;
                } else {
                    if (node.val % 2 == 1 || node.val >= prev) return false;
                }
                prev = node.val;
                if (node.left != null) queue.offer(node.left);
                if (node.right != null) queue.offer(node.right);
            }
            level++;
        }
        return true;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(10, new TreeNode(3, new TreeNode(12), new TreeNode(8)), null),
                new TreeNode(4, new TreeNode(7), new TreeNode(9)));
        System.out.println("Test 1: " + isEvenOddTree(t1)); // true

        TreeNode t2 = new TreeNode(5, new TreeNode(4, new TreeNode(3), new TreeNode(3)), new TreeNode(2, new TreeNode(7), null));
        System.out.println("Test 2: " + isEvenOddTree(t2)); // false

        System.out.println("Test 3: " + isEvenOddTree(new TreeNode(1))); // true
    }
}

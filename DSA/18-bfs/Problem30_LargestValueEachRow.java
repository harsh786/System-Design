import java.util.*;

/**
 * Problem: Find Largest Value in Each Tree Row (LeetCode 515)
 * Approach: BFS level order, track max per level
 * Time: O(N), Space: O(W) width of tree
 * Production Analogy: Finding peak load per tier in multi-tier architecture
 */
public class Problem30_LargestValueEachRow {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<Integer> largestValues(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        if (root == null) return res;
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            int size = q.size(), max = Integer.MIN_VALUE;
            for (int i = 0; i < size; i++) {
                TreeNode node = q.poll();
                max = Math.max(max, node.val);
                if (node.left != null) q.offer(node.left);
                if (node.right != null) q.offer(node.right);
            }
            res.add(max);
        }
        return res;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(3); root.right = new TreeNode(2);
        root.left.left = new TreeNode(5); root.left.right = new TreeNode(3); root.right.right = new TreeNode(9);
        System.out.println(new Problem30_LargestValueEachRow().largestValues(root)); // [1,3,9]
    }
}

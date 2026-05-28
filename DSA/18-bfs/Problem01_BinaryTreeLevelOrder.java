import java.util.*;

/**
 * Problem: Binary Tree Level Order Traversal (LeetCode 102)
 * Approach: BFS with queue, process level by level using size
 * Time: O(N), Space: O(N)
 * Production Analogy: Processing organizational hierarchy level by level for notifications
 */
public class Problem01_BinaryTreeLevelOrder {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<List<Integer>> levelOrder(TreeNode root) {
        List<List<Integer>> res = new ArrayList<>();
        if (root == null) return res;
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            int size = q.size();
            List<Integer> level = new ArrayList<>();
            for (int i = 0; i < size; i++) {
                TreeNode node = q.poll();
                level.add(node.val);
                if (node.left != null) q.offer(node.left);
                if (node.right != null) q.offer(node.right);
            }
            res.add(level);
        }
        return res;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(9); root.right = new TreeNode(20);
        root.right.left = new TreeNode(15); root.right.right = new TreeNode(7);
        System.out.println(new Problem01_BinaryTreeLevelOrder().levelOrder(root));
    }
}

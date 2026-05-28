import java.util.*;

/**
 * Problem: Minimum Depth of Binary Tree (LeetCode 111)
 * Approach: BFS - first leaf encountered gives minimum depth
 * Time: O(N), Space: O(W)
 * Production Analogy: Finding quickest path to terminal state in decision tree
 */
public class Problem32_MinimumDepthBinaryTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public int minDepth(TreeNode root) {
        if (root == null) return 0;
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        int depth = 0;
        while (!q.isEmpty()) {
            depth++;
            int size = q.size();
            for (int i = 0; i < size; i++) {
                TreeNode node = q.poll();
                if (node.left == null && node.right == null) return depth;
                if (node.left != null) q.offer(node.left);
                if (node.right != null) q.offer(node.right);
            }
        }
        return depth;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(9); root.right = new TreeNode(20);
        root.right.left = new TreeNode(15); root.right.right = new TreeNode(7);
        System.out.println(new Problem32_MinimumDepthBinaryTree().minDepth(root)); // 2
    }
}

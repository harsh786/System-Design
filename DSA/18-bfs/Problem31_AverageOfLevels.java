import java.util.*;

/**
 * Problem: Average of Levels in Binary Tree (LeetCode 637)
 * Approach: BFS level order computing average per level
 * Time: O(N), Space: O(W)
 * Production Analogy: Computing average latency per service tier
 */
public class Problem31_AverageOfLevels {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<Double> averageOfLevels(TreeNode root) {
        List<Double> res = new ArrayList<>();
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            int size = q.size(); double sum = 0;
            for (int i = 0; i < size; i++) {
                TreeNode node = q.poll();
                sum += node.val;
                if (node.left != null) q.offer(node.left);
                if (node.right != null) q.offer(node.right);
            }
            res.add(sum / size);
        }
        return res;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(9); root.right = new TreeNode(20);
        root.right.left = new TreeNode(15); root.right.right = new TreeNode(7);
        System.out.println(new Problem31_AverageOfLevels().averageOfLevels(root));
    }
}

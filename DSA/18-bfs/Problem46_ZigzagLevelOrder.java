import java.util.*;

/**
 * Problem: Binary Tree Zigzag Level Order Traversal (LeetCode 103)
 * Approach: BFS with alternating direction per level
 * Time: O(N), Space: O(N)
 * Production Analogy: Alternating read patterns across storage tiers for load balancing
 */
public class Problem46_ZigzagLevelOrder {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<List<Integer>> zigzagLevelOrder(TreeNode root) {
        List<List<Integer>> res = new ArrayList<>();
        if (root == null) return res;
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        boolean leftToRight = true;
        while (!q.isEmpty()) {
            int size = q.size();
            LinkedList<Integer> level = new LinkedList<>();
            for (int i = 0; i < size; i++) {
                TreeNode node = q.poll();
                if (leftToRight) level.addLast(node.val); else level.addFirst(node.val);
                if (node.left != null) q.offer(node.left);
                if (node.right != null) q.offer(node.right);
            }
            res.add(level);
            leftToRight = !leftToRight;
        }
        return res;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(9); root.right = new TreeNode(20);
        root.right.left = new TreeNode(15); root.right.right = new TreeNode(7);
        System.out.println(new Problem46_ZigzagLevelOrder().zigzagLevelOrder(root));
    }
}

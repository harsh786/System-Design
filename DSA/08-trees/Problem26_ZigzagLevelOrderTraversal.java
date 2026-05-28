import java.util.*;
/**
 * Problem 26: Binary Tree Zigzag Level Order Traversal (LeetCode 103)
 * 
 * Approach: BFS with flag to alternate direction. Use deque or reverse alternate levels.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Alternating read direction in a multi-level cache hierarchy for load balancing.
 */
public class Problem26_ZigzagLevelOrderTraversal {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<List<Integer>> zigzagLevelOrder(TreeNode root) {
        List<List<Integer>> result = new ArrayList<>();
        if (root == null) return result;
        Queue<TreeNode> queue = new LinkedList<>();
        queue.offer(root);
        boolean leftToRight = true;
        while (!queue.isEmpty()) {
            int size = queue.size();
            LinkedList<Integer> level = new LinkedList<>();
            for (int i = 0; i < size; i++) {
                TreeNode node = queue.poll();
                if (leftToRight) level.addLast(node.val);
                else level.addFirst(node.val);
                if (node.left != null) queue.offer(node.left);
                if (node.right != null) queue.offer(node.right);
            }
            result.add(level);
            leftToRight = !leftToRight;
        }
        return result;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(3, new TreeNode(9), new TreeNode(20, new TreeNode(15), new TreeNode(7)));
        System.out.println("Test 1: " + zigzagLevelOrder(t1)); // [[3],[20,9],[15,7]]
        System.out.println("Test 2: " + zigzagLevelOrder(new TreeNode(1))); // [[1]]
        System.out.println("Test 3: " + zigzagLevelOrder(null)); // []
    }
}

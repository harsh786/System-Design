import java.util.*;
/**
 * Problem 4: Binary Tree Level Order Traversal (LeetCode 102)
 * 
 * Approach: BFS with queue, process level by level.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Processing service dependency graph level by level for
 * ordered startup/shutdown of microservices.
 */
public class Problem04_BinaryTreeLevelOrderTraversal {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<List<Integer>> levelOrder(TreeNode root) {
        List<List<Integer>> result = new ArrayList<>();
        if (root == null) return result;
        Queue<TreeNode> queue = new LinkedList<>();
        queue.offer(root);
        while (!queue.isEmpty()) {
            int size = queue.size();
            List<Integer> level = new ArrayList<>();
            for (int i = 0; i < size; i++) {
                TreeNode node = queue.poll();
                level.add(node.val);
                if (node.left != null) queue.offer(node.left);
                if (node.right != null) queue.offer(node.right);
            }
            result.add(level);
        }
        return result;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(3, new TreeNode(9), new TreeNode(20, new TreeNode(15), new TreeNode(7)));
        System.out.println("Test 1: " + levelOrder(t1)); // [[3],[9,20],[15,7]]
        System.out.println("Test 2: " + levelOrder(null)); // []
        System.out.println("Test 3: " + levelOrder(new TreeNode(1))); // [[1]]
    }
}

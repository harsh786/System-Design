import java.util.*;
/**
 * Problem 25: Binary Tree Right Side View (LeetCode 199)
 * 
 * Approach: BFS, take last element of each level. Or DFS with right-first traversal.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Showing only the most recently deployed version at each service tier in a dashboard.
 */
public class Problem25_BinaryTreeRightSideView {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<Integer> rightSideView(TreeNode root) {
        List<Integer> result = new ArrayList<>();
        if (root == null) return result;
        Queue<TreeNode> queue = new LinkedList<>();
        queue.offer(root);
        while (!queue.isEmpty()) {
            int size = queue.size();
            for (int i = 0; i < size; i++) {
                TreeNode node = queue.poll();
                if (i == size - 1) result.add(node.val);
                if (node.left != null) queue.offer(node.left);
                if (node.right != null) queue.offer(node.right);
            }
        }
        return result;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, null, new TreeNode(5)), new TreeNode(3, null, new TreeNode(4)));
        System.out.println("Test 1: " + rightSideView(t1)); // [1,3,4]

        TreeNode t2 = new TreeNode(1, new TreeNode(2, new TreeNode(4), null), new TreeNode(3));
        System.out.println("Test 2: " + rightSideView(t2)); // [1,3,4]

        System.out.println("Test 3: " + rightSideView(null)); // []
    }
}

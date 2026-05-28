import java.util.*;
/**
 * Problem 47: Maximum Width of Binary Tree (LeetCode 662)
 * 
 * Approach: BFS with position indexing. Root=0, left=2*i, right=2*i+1.
 * Width of level = rightmost - leftmost + 1.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Determining max parallelism possible at any level of a task execution DAG.
 */
public class Problem47_MaxWidthOfBinaryTree {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int widthOfBinaryTree(TreeNode root) {
        if (root == null) return 0;
        int maxWidth = 0;
        Queue<long[]> queue = new LinkedList<>(); // [node_hash, index]
        // We'll use a parallel queue for nodes
        Queue<TreeNode> nodeQueue = new LinkedList<>();
        nodeQueue.offer(root);
        queue.offer(new long[]{0});
        while (!nodeQueue.isEmpty()) {
            int size = nodeQueue.size();
            long left = 0, right = 0;
            for (int i = 0; i < size; i++) {
                TreeNode node = nodeQueue.poll();
                long[] info = queue.poll();
                long idx = info[0];
                if (i == 0) left = idx;
                if (i == size - 1) right = idx;
                if (node.left != null) { nodeQueue.offer(node.left); queue.offer(new long[]{2 * idx}); }
                if (node.right != null) { nodeQueue.offer(node.right); queue.offer(new long[]{2 * idx + 1}); }
            }
            maxWidth = Math.max(maxWidth, (int)(right - left + 1));
        }
        return maxWidth;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(3, new TreeNode(5), new TreeNode(3)), new TreeNode(2, null, new TreeNode(9)));
        System.out.println("Test 1: " + widthOfBinaryTree(t1)); // 4

        TreeNode t2 = new TreeNode(1, new TreeNode(3, new TreeNode(5), null), null);
        System.out.println("Test 2: " + widthOfBinaryTree(t2)); // 1 (only one node at deepest)

        System.out.println("Test 3: " + widthOfBinaryTree(new TreeNode(1))); // 1
    }
}

import java.util.*;

/**
 * Problem: Binary Tree Right Side View (LeetCode 199)
 * Approach: BFS - take last element of each level
 * Time: O(N), Space: O(W)
 * Production Analogy: Viewing the rightmost active service at each tier from client perspective
 */
public class Problem34_BinaryTreeRightSideView {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<Integer> rightSideView(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        if (root == null) return res;
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                TreeNode node = q.poll();
                if (i == size - 1) res.add(node.val);
                if (node.left != null) q.offer(node.left);
                if (node.right != null) q.offer(node.right);
            }
        }
        return res;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.right = new TreeNode(5); root.right.right = new TreeNode(4);
        System.out.println(new Problem34_BinaryTreeRightSideView().rightSideView(root)); // [1,3,4]
    }
}

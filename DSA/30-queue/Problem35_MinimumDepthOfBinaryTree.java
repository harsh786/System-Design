import java.util.*;

public class Problem35_MinimumDepthOfBinaryTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static int minDepth(TreeNode root) {
        if (root == null) return 0;
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root); int depth = 0;
        while (!q.isEmpty()) {
            depth++;
            for (int sz = q.size(); sz > 0; sz--) {
                TreeNode n = q.poll();
                if (n.left == null && n.right == null) return depth;
                if (n.left != null) q.offer(n.left);
                if (n.right != null) q.offer(n.right);
            }
        }
        return depth;
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(9); root.right = new TreeNode(20);
        root.right.left = new TreeNode(15); root.right.right = new TreeNode(7);
        System.out.println(minDepth(root)); // 2
    }
}

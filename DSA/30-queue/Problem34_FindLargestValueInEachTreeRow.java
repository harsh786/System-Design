import java.util.*;

public class Problem34_FindLargestValueInEachTreeRow {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static List<Integer> largestValues(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        if (root == null) return res;
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            int max = Integer.MIN_VALUE;
            for (int sz = q.size(); sz > 0; sz--) {
                TreeNode n = q.poll(); max = Math.max(max, n.val);
                if (n.left != null) q.offer(n.left);
                if (n.right != null) q.offer(n.right);
            }
            res.add(max);
        }
        return res;
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(3); root.right = new TreeNode(2);
        root.left.left = new TreeNode(5); root.left.right = new TreeNode(3); root.right.right = new TreeNode(9);
        System.out.println(largestValues(root)); // [1,3,9]
    }
}

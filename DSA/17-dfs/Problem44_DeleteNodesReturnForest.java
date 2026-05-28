import java.util.*;

/**
 * Problem: Delete Nodes And Return Forest (LeetCode 1110)
 * Approach: DFS post-order - if node is deleted, its children become new roots
 * Time: O(N), Space: O(N)
 * Production Analogy: Decomposing a monolith - removing services creates independent sub-systems
 */
public class Problem44_DeleteNodesReturnForest {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<TreeNode> delNodes(TreeNode root, int[] to_delete) {
        Set<Integer> toDelete = new HashSet<>();
        for (int d : to_delete) toDelete.add(d);
        List<TreeNode> res = new ArrayList<>();
        root = dfs(root, toDelete, res);
        if (root != null) res.add(root);
        return res;
    }

    private TreeNode dfs(TreeNode node, Set<Integer> toDelete, List<TreeNode> res) {
        if (node == null) return null;
        node.left = dfs(node.left, toDelete, res);
        node.right = dfs(node.right, toDelete, res);
        if (toDelete.contains(node.val)) {
            if (node.left != null) res.add(node.left);
            if (node.right != null) res.add(node.right);
            return null;
        }
        return node;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.left = new TreeNode(4); root.left.right = new TreeNode(5);
        root.right.left = new TreeNode(6); root.right.right = new TreeNode(7);
        List<TreeNode> forest = new Problem44_DeleteNodesReturnForest().delNodes(root, new int[]{3,5});
        System.out.println("Forest size: " + forest.size()); // 3
    }
}

import java.util.*;
/**
 * Problem 38: Delete Nodes And Return Forest (LeetCode 1110)
 * 
 * Approach: DFS. If node is to be deleted, its children become new roots (if not null).
 * Return null to parent if deleted.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Removing specific services from a dependency tree and identifying
 * the resulting independent service clusters.
 */
public class Problem38_DeleteNodesReturnForest {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<TreeNode> delNodes(TreeNode root, int[] to_delete) {
        Set<Integer> toDelete = new HashSet<>();
        for (int d : to_delete) toDelete.add(d);
        List<TreeNode> forest = new ArrayList<>();
        root = dfs(root, toDelete, forest);
        if (root != null) forest.add(root);
        return forest;
    }

    private static TreeNode dfs(TreeNode node, Set<Integer> toDelete, List<TreeNode> forest) {
        if (node == null) return null;
        node.left = dfs(node.left, toDelete, forest);
        node.right = dfs(node.right, toDelete, forest);
        if (toDelete.contains(node.val)) {
            if (node.left != null) forest.add(node.left);
            if (node.right != null) forest.add(node.right);
            return null;
        }
        return node;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)),
                new TreeNode(3, new TreeNode(6), new TreeNode(7)));
        List<TreeNode> res = delNodes(t1, new int[]{3, 5});
        System.out.print("Test 1 roots: ");
        for (TreeNode n : res) System.out.print(n.val + " ");
        System.out.println(); // 1 6 7

        List<TreeNode> res2 = delNodes(new TreeNode(1, new TreeNode(2), null), new int[]{1});
        System.out.println("Test 2: " + res2.get(0).val); // 2
    }
}

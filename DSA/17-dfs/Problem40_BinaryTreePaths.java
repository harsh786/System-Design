import java.util.*;

/**
 * Problem: Binary Tree Paths (LeetCode 257)
 * Approach: DFS collecting root-to-leaf paths as strings
 * Time: O(N), Space: O(N)
 * Production Analogy: Tracing all request paths through a decision tree service
 */
public class Problem40_BinaryTreePaths {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<String> binaryTreePaths(TreeNode root) {
        List<String> res = new ArrayList<>();
        if (root != null) dfs(root, "", res);
        return res;
    }

    private void dfs(TreeNode node, String path, List<String> res) {
        String cur = path + node.val;
        if (node.left == null && node.right == null) { res.add(cur); return; }
        if (node.left != null) dfs(node.left, cur + "->", res);
        if (node.right != null) dfs(node.right, cur + "->", res);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.right = new TreeNode(5);
        System.out.println(new Problem40_BinaryTreePaths().binaryTreePaths(root));
    }
}

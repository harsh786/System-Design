import java.util.*;
/**
 * Problem 41: Binary Tree Paths (LeetCode 257)
 * 
 * Approach: DFS backtracking, build path string, add to result at leaves.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Enumerating all possible request routing paths through a service mesh.
 */
public class Problem41_BinaryTreePaths {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static List<String> binaryTreePaths(TreeNode root) {
        List<String> result = new ArrayList<>();
        if (root != null) dfs(root, "", result);
        return result;
    }

    private static void dfs(TreeNode node, String path, List<String> result) {
        path += node.val;
        if (node.left == null && node.right == null) { result.add(path); return; }
        if (node.left != null) dfs(node.left, path + "->", result);
        if (node.right != null) dfs(node.right, path + "->", result);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, null, new TreeNode(5)), new TreeNode(3));
        System.out.println("Test 1: " + binaryTreePaths(t1)); // ["1->2->5", "1->3"]
        System.out.println("Test 2: " + binaryTreePaths(new TreeNode(1))); // ["1"]
        System.out.println("Test 3: " + binaryTreePaths(null)); // []
    }
}

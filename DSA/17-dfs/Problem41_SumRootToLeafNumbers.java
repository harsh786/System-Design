/**
 * Problem: Sum Root to Leaf Numbers (LeetCode 129)
 * Approach: DFS passing accumulated number down to leaves
 * Time: O(N), Space: O(H)
 * Production Analogy: Aggregating hierarchical cost codes from organizational tree
 */
public class Problem41_SumRootToLeafNumbers {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public int sumNumbers(TreeNode root) {
        return dfs(root, 0);
    }

    private int dfs(TreeNode node, int num) {
        if (node == null) return 0;
        num = num * 10 + node.val;
        if (node.left == null && node.right == null) return num;
        return dfs(node.left, num) + dfs(node.right, num);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.left = new TreeNode(2); root.right = new TreeNode(3);
        System.out.println(new Problem41_SumRootToLeafNumbers().sumNumbers(root)); // 12+13=25
    }
}

/**
 * Problem 40: Sum Root to Leaf Numbers (LeetCode 129)
 * 
 * Approach: DFS passing accumulated number. At leaf, add to total.
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Summing all possible route IDs formed by concatenating node identifiers root-to-leaf.
 */
public class Problem40_SumRootToLeafNumbers {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int sumNumbers(TreeNode root) {
        return dfs(root, 0);
    }

    private static int dfs(TreeNode node, int num) {
        if (node == null) return 0;
        num = num * 10 + node.val;
        if (node.left == null && node.right == null) return num;
        return dfs(node.left, num) + dfs(node.right, num);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2), new TreeNode(3));
        System.out.println("Test 1: " + sumNumbers(t1)); // 25 (12+13)

        TreeNode t2 = new TreeNode(4, new TreeNode(9, new TreeNode(5), new TreeNode(1)), new TreeNode(0));
        System.out.println("Test 2: " + sumNumbers(t2)); // 1026 (495+491+40)

        System.out.println("Test 3: " + sumNumbers(new TreeNode(0))); // 0
    }
}

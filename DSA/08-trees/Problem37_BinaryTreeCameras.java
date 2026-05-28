/**
 * Problem 37: Binary Tree Cameras (LeetCode 968)
 * 
 * Approach: Greedy DFS from bottom. Each node returns state:
 * 0 = needs coverage, 1 = has camera, 2 = covered.
 * Place camera at parent of uncovered leaf (greedy).
 * Time: O(n), Space: O(h)
 * 
 * Production Analogy: Minimum number of monitoring agents to cover all services in a dependency tree.
 */
public class Problem37_BinaryTreeCameras {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static int cameras;

    public static int minCameraCover(TreeNode root) {
        cameras = 0;
        if (dfs(root) == 0) cameras++; // root needs coverage
        return cameras;
    }

    // 0=needs cover, 1=has camera, 2=covered
    private static int dfs(TreeNode node) {
        if (node == null) return 2; // null nodes are "covered"
        int left = dfs(node.left);
        int right = dfs(node.right);
        if (left == 0 || right == 0) { cameras++; return 1; } // must place camera here
        if (left == 1 || right == 1) return 2; // covered by child camera
        return 0; // needs coverage from parent
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(0, new TreeNode(0, new TreeNode(0), new TreeNode(0)), null);
        System.out.println("Test 1: " + minCameraCover(t1)); // 1

        TreeNode t2 = new TreeNode(0, new TreeNode(0, new TreeNode(0, new TreeNode(0, null, new TreeNode(0)), null), null), null);
        System.out.println("Test 2: " + minCameraCover(t2)); // 2

        System.out.println("Test 3 (single): " + minCameraCover(new TreeNode(0))); // 1
    }
}

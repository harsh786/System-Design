/**
 * Problem 15: Kth Smallest Element in a BST (LeetCode 230)
 * 
 * Approach: Inorder traversal of BST gives sorted order. Count to k.
 * Time: O(h + k), Space: O(h)
 * 
 * Production Analogy: Finding the kth percentile latency from a sorted index of response times.
 */
public class Problem15_KthSmallestInBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static int count, result;

    public static int kthSmallest(TreeNode root, int k) {
        count = 0; result = 0;
        inorder(root, k);
        return result;
    }

    private static void inorder(TreeNode node, int k) {
        if (node == null) return;
        inorder(node.left, k);
        if (++count == k) { result = node.val; return; }
        inorder(node.right, k);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(3, new TreeNode(1, null, new TreeNode(2)), new TreeNode(4));
        System.out.println("Test 1 (k=1): " + kthSmallest(t1, 1)); // 1
        System.out.println("Test 2 (k=3): " + kthSmallest(t1, 3)); // 3

        TreeNode t2 = new TreeNode(5, new TreeNode(3, new TreeNode(2, new TreeNode(1), null), new TreeNode(4)), new TreeNode(6));
        System.out.println("Test 3 (k=3): " + kthSmallest(t2, 3)); // 3
    }
}

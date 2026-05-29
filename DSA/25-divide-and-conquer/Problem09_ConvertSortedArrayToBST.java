/**
 * Problem 9: Convert Sorted Array to BST (LeetCode 108)
 * 
 * D&C Approach:
 * - DIVIDE: Pick middle element as root (ensures height balance)
 * - CONQUER: Left subarray becomes left subtree, right becomes right subtree
 * - COMBINE: Connect subtrees to root
 * 
 * Recurrence: T(n) = 2T(n/2) + O(1)
 * Time: O(n), Space: O(log n) recursion stack
 * 
 * Production Analogy:
 * - Building balanced search indexes from sorted data (B-tree bulk loading)
 * - Constructing routing tables in CDNs for balanced request distribution
 */
public class Problem09_ConvertSortedArrayToBST {

    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int val) { this.val = val; }
    }

    public static TreeNode sortedArrayToBST(int[] nums) {
        return build(nums, 0, nums.length - 1);
    }

    private static TreeNode build(int[] nums, int left, int right) {
        if (left > right) return null;
        int mid = left + (right - left) / 2;
        TreeNode node = new TreeNode(nums[mid]);
        node.left = build(nums, left, mid - 1);
        node.right = build(nums, mid + 1, right);
        return node;
    }

    private static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    private static int height(TreeNode root) {
        if (root == null) return 0;
        return 1 + Math.max(height(root.left), height(root.right));
    }

    public static void main(String[] args) {
        TreeNode t1 = sortedArrayToBST(new int[]{-10,-3,0,5,9});
        printInorder(t1); System.out.println(" height=" + height(t1));
        
        TreeNode t2 = sortedArrayToBST(new int[]{1,3});
        printInorder(t2); System.out.println(" height=" + height(t2));
        
        TreeNode t3 = sortedArrayToBST(new int[]{1});
        printInorder(t3); System.out.println(" height=" + height(t3));
        
        TreeNode t4 = sortedArrayToBST(new int[]{1,2,3,4,5,6,7});
        printInorder(t4); System.out.println(" height=" + height(t4));
    }
}

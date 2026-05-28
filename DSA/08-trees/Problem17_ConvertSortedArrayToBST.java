/**
 * Problem 17: Convert Sorted Array to Binary Search Tree (LeetCode 108)
 * 
 * Approach: Pick middle element as root, recurse on left and right halves.
 * Time: O(n), Space: O(log n)
 * 
 * Production Analogy: Building balanced search indexes from sorted data during bulk import.
 */
public class Problem17_ConvertSortedArrayToBST {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
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

    static void printPreorder(TreeNode root) {
        if (root == null) return;
        System.out.print(root.val + " ");
        printPreorder(root.left);
        printPreorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = sortedArrayToBST(new int[]{-10,-3,0,5,9});
        System.out.print("Test 1: "); printPreorder(t1); System.out.println(); // 0 -10 -3 5 9 or similar balanced

        TreeNode t2 = sortedArrayToBST(new int[]{1,3});
        System.out.print("Test 2: "); printPreorder(t2); System.out.println();

        TreeNode t3 = sortedArrayToBST(new int[]{1});
        System.out.println("Test 3: " + t3.val); // 1
    }
}

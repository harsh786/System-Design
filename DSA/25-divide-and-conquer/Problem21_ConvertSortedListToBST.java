/**
 * Problem 21: Convert Sorted List to BST (LeetCode 109)
 * 
 * D&C Approach:
 * - DIVIDE: Find middle of list (slow/fast pointer), split into two halves
 * - CONQUER: Recursively build BST from each half
 * - COMBINE: Middle becomes root, connect left/right subtrees
 * 
 * Time: O(n log n) with find-middle approach, O(n) with inorder simulation
 * Space: O(log n) for balanced tree height
 * 
 * Production Analogy:
 * - Building balanced index from sequential scan of sorted data on disk
 * - Constructing search tree from streaming sorted input
 */
public class Problem21_ConvertSortedListToBST {

    static class ListNode { int val; ListNode next; ListNode(int v) { val = v; } }
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    // O(n) approach using inorder simulation
    private static ListNode current;

    public static TreeNode sortedListToBST(ListNode head) {
        int size = 0;
        ListNode p = head;
        while (p != null) { size++; p = p.next; }
        current = head;
        return buildTree(0, size - 1);
    }

    private static TreeNode buildTree(int lo, int hi) {
        if (lo > hi) return null;
        int mid = lo + (hi - lo) / 2;
        TreeNode left = buildTree(lo, mid - 1);
        TreeNode node = new TreeNode(current.val);
        current = current.next;
        node.left = left;
        node.right = buildTree(mid + 1, hi);
        return node;
    }

    private static ListNode buildList(int[] arr) {
        ListNode dummy = new ListNode(0), c = dummy;
        for (int v : arr) { c.next = new ListNode(v); c = c.next; }
        return dummy.next;
    }

    private static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        TreeNode t1 = sortedListToBST(buildList(new int[]{-10,-3,0,5,9}));
        printInorder(t1); System.out.println();

        TreeNode t2 = sortedListToBST(buildList(new int[]{1,2,3}));
        printInorder(t2); System.out.println();

        TreeNode t3 = sortedListToBST(buildList(new int[]{}));
        printInorder(t3); System.out.println();
    }
}

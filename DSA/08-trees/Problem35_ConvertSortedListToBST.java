/**
 * Problem 35: Convert Sorted List to Binary Search Tree (LeetCode 109)
 * 
 * Approach: Find middle of list (slow/fast pointer), make it root, recurse on halves.
 * Time: O(n log n), Space: O(log n)
 * 
 * Production Analogy: Building a balanced search tree from a streaming sorted data source.
 */
public class Problem35_ConvertSortedListToBST {
    static class ListNode {
        int val;
        ListNode next;
        ListNode(int v) { val = v; }
        ListNode(int v, ListNode n) { val = v; next = n; }
    }
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
    }

    public static TreeNode sortedListToBST(ListNode head) {
        if (head == null) return null;
        if (head.next == null) return new TreeNode(head.val);
        ListNode prev = null, slow = head, fast = head;
        while (fast != null && fast.next != null) {
            prev = slow; slow = slow.next; fast = fast.next.next;
        }
        prev.next = null; // cut list
        TreeNode root = new TreeNode(slow.val);
        root.left = sortedListToBST(head);
        root.right = sortedListToBST(slow.next);
        return root;
    }

    static void printInorder(TreeNode root) {
        if (root == null) return;
        printInorder(root.left);
        System.out.print(root.val + " ");
        printInorder(root.right);
    }

    public static void main(String[] args) {
        ListNode head = new ListNode(-10, new ListNode(-3, new ListNode(0, new ListNode(5, new ListNode(9)))));
        TreeNode t = sortedListToBST(head);
        System.out.print("Test 1: "); printInorder(t); System.out.println(); // -10 -3 0 5 9

        System.out.println("Test 2 (null): " + sortedListToBST(null)); // null

        TreeNode t2 = sortedListToBST(new ListNode(1));
        System.out.println("Test 3: " + t2.val); // 1
    }
}

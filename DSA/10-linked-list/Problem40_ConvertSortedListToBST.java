/**
 * Problem 40: Convert Sorted List to Binary Search Tree
 * 
 * Approach: Find middle (slow/fast), use as root, recurse on left/right halves.
 * Time Complexity: O(n log n)
 * Space Complexity: O(log n)
 * 
 * Production Analogy: Building a balanced search index from sorted data - the
 * median becomes the root for optimal query performance.
 */
public class Problem40_ConvertSortedListToBST {
    static class ListNode {
        int val; ListNode next;
        ListNode(int val) { this.val = val; }
        ListNode(int val, ListNode next) { this.val = val; this.next = next; }
    }
    static class TreeNode {
        int val; TreeNode left, right;
        TreeNode(int v) { val = v; }
    }

    public static TreeNode sortedListToBST(ListNode head) {
        if (head == null) return null;
        if (head.next == null) return new TreeNode(head.val);
        ListNode prev = null, slow = head, fast = head;
        while (fast != null && fast.next != null) { prev = slow; slow = slow.next; fast = fast.next.next; }
        if (prev != null) prev.next = null;
        TreeNode root = new TreeNode(slow.val);
        root.left = sortedListToBST(head == slow ? null : head);
        root.right = sortedListToBST(slow.next);
        return root;
    }

    static void inorder(TreeNode root) {
        if (root == null) return;
        inorder(root.left);
        System.out.print(root.val + " ");
        inorder(root.right);
    }

    public static void main(String[] args) {
        ListNode h = new ListNode(-10, new ListNode(-3, new ListNode(0, new ListNode(5, new ListNode(9)))));
        TreeNode root = sortedListToBST(h);
        System.out.print("Inorder: "); inorder(root); System.out.println(); // -10 -3 0 5 9
        System.out.println("Root: " + root.val); // 0
    }
}

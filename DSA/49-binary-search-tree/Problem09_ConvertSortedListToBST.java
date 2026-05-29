public class Problem09_ConvertSortedListToBST {
    static class ListNode { int val; ListNode next; ListNode(int v) { val = v; } }
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static TreeNode sortedListToBST(ListNode head) {
        if (head == null) return null;
        if (head.next == null) return new TreeNode(head.val);
        ListNode slow = head, fast = head, prev = null;
        while (fast != null && fast.next != null) { prev = slow; slow = slow.next; fast = fast.next.next; }
        if (prev != null) prev.next = null;
        TreeNode root = new TreeNode(slow.val);
        root.left = sortedListToBST(head == slow ? null : head);
        root.right = sortedListToBST(slow.next);
        return root;
    }

    static void inorder(TreeNode n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        ListNode head = new ListNode(-10);
        head.next = new ListNode(-3); head.next.next = new ListNode(0);
        head.next.next.next = new ListNode(5); head.next.next.next.next = new ListNode(9);
        TreeNode root = sortedListToBST(head);
        inorder(root); System.out.println();
    }
}

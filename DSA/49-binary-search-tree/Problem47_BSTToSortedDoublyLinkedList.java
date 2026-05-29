public class Problem47_BSTToSortedDoublyLinkedList {
    static class Node { int val; Node left, right; Node(int v) { val = v; } }
    static Node head, prev2;

    public static Node treeToDoublyList(Node root) {
        if (root == null) return null;
        head = null; prev2 = null;
        inorder(root);
        prev2.right = head; head.left = prev2;
        return head;
    }

    private static void inorder(Node n) {
        if (n == null) return;
        inorder(n.left);
        if (prev2 == null) head = n;
        else { prev2.right = n; n.left = prev2; }
        prev2 = n;
        inorder(n.right);
    }

    public static void main(String[] args) {
        Node root = new Node(4);
        root.left = new Node(2); root.right = new Node(5);
        root.left.left = new Node(1); root.left.right = new Node(3);
        Node h = treeToDoublyList(root);
        Node cur = h;
        for (int i = 0; i < 5; i++) { System.out.print(cur.val + " "); cur = cur.right; }
        System.out.println(); // 1 2 3 4 5
    }
}

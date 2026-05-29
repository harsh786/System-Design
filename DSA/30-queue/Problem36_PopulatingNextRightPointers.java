import java.util.*;

public class Problem36_PopulatingNextRightPointers {
    static class Node { int val; Node left, right, next; Node(int v) { val = v; } }
    public static Node connect(Node root) {
        if (root == null) return null;
        Queue<Node> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            Node prev = null;
            for (int sz = q.size(); sz > 0; sz--) {
                Node n = q.poll();
                if (prev != null) prev.next = n;
                prev = n;
                if (n.left != null) q.offer(n.left);
                if (n.right != null) q.offer(n.right);
            }
        }
        return root;
    }
    public static void main(String[] args) {
        Node root = new Node(1); root.left = new Node(2); root.right = new Node(3);
        root.left.left = new Node(4); root.left.right = new Node(5); root.right.right = new Node(7);
        connect(root);
        System.out.println(root.left.next.val); // 3
    }
}

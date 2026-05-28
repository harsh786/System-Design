import java.util.*;

/**
 * Problem: Populating Next Right Pointers in Each Node (LeetCode 116)
 * Approach: BFS level order - connect nodes at same level
 * Time: O(N), Space: O(W)
 * Production Analogy: Setting up peer-to-peer links between same-tier services
 */
public class Problem33_PopulatingNextRightPointers {
    static class Node { int val; Node left, right, next; Node(int v) { val = v; } }

    public Node connect(Node root) {
        if (root == null) return null;
        Queue<Node> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            int size = q.size();
            Node prev = null;
            for (int i = 0; i < size; i++) {
                Node node = q.poll();
                if (prev != null) prev.next = node;
                prev = node;
                if (node.left != null) q.offer(node.left);
                if (node.right != null) q.offer(node.right);
            }
        }
        return root;
    }

    public static void main(String[] args) {
        Node root = new Node(1); root.left = new Node(2); root.right = new Node(3);
        root.left.left = new Node(4); root.left.right = new Node(5);
        root.right.left = new Node(6); root.right.right = new Node(7);
        new Problem33_PopulatingNextRightPointers().connect(root);
        System.out.println(root.left.next.val); // 3
    }
}

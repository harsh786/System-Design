import java.util.*;

public class Problem15_RandomizedTreap {
    static Random rand = new Random();
    static class Node {
        int key, priority; Node left, right;
        Node(int k) { key = k; priority = rand.nextInt(); }
    }

    static Node rotateRight(Node p) { Node q = p.left; p.left = q.right; q.right = p; return q; }
    static Node rotateLeft(Node p) { Node q = p.right; p.right = q.left; q.left = p; return q; }

    static Node insert(Node root, int key) {
        if (root == null) return new Node(key);
        if (key < root.key) { root.left = insert(root.left, key); if (root.left.priority > root.priority) root = rotateRight(root); }
        else { root.right = insert(root.right, key); if (root.right.priority > root.priority) root = rotateLeft(root); }
        return root;
    }

    static void inorder(Node root) { if (root != null) { inorder(root.left); System.out.print(root.key+" "); inorder(root.right); } }

    public static void main(String[] args) {
        Node root = null;
        for (int v : new int[]{5,2,8,1,4,7,9}) root = insert(root, v);
        inorder(root); System.out.println();
    }
}

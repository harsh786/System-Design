import java.util.*;

public class Problem41_TreapInsertDeleteSearch {
    static Random rand = new Random(42);
    static class Node { int key, priority, size; Node left, right; Node(int k) { key = k; priority = rand.nextInt(); size = 1; } }
    static int size(Node n) { return n == null ? 0 : n.size; }
    static void update(Node n) { if (n != null) n.size = 1 + size(n.left) + size(n.right); }

    static Node[] split(Node t, int key) {
        if (t == null) return new Node[]{null, null};
        if (t.key <= key) { Node[] r = split(t.right, key); t.right = r[0]; update(t); return new Node[]{t, r[1]}; }
        else { Node[] r = split(t.left, key); t.left = r[1]; update(t); return new Node[]{r[0], t}; }
    }

    static Node merge(Node l, Node r) {
        if (l == null) return r; if (r == null) return l;
        if (l.priority > r.priority) { l.right = merge(l.right, r); update(l); return l; }
        else { r.left = merge(l, r.left); update(r); return r; }
    }

    static Node insert(Node root, int key) {
        Node[] s = split(root, key - 1);
        return merge(merge(s[0], new Node(key)), s[1]);
    }

    static Node delete(Node root, int key) {
        Node[] s1 = split(root, key - 1);
        Node[] s2 = split(s1[1], key);
        // s2[0] contains nodes with key == key, remove one
        if (s2[0] != null) s2[0] = merge(s2[0].left, s2[0].right);
        return merge(merge(s1[0], s2[0]), s2[1]);
    }

    static boolean search(Node root, int key) {
        if (root == null) return false;
        if (root.key == key) return true;
        return key < root.key ? search(root.left, key) : search(root.right, key);
    }

    static void inorder(Node n) { if (n != null) { inorder(n.left); System.out.print(n.key + " "); inorder(n.right); } }

    public static void main(String[] args) {
        Node root = null;
        for (int v : new int[]{5, 2, 8, 1, 4, 7, 10}) root = insert(root, v);
        inorder(root); System.out.println();
        System.out.println(search(root, 4)); // true
        root = delete(root, 5);
        inorder(root); System.out.println(); // 1 2 4 7 8 10
    }
}

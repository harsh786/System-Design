public class Problem49_CountNodesInRange {
    static class Node { int val, size; Node left, right; Node(int v) { val = v; size = 1; } }
    static int size(Node n) { return n == null ? 0 : n.size; }

    static Node insert(Node root, int val) {
        if (root == null) return new Node(val);
        if (val < root.val) root.left = insert(root.left, val);
        else root.right = insert(root.right, val);
        root.size = 1 + size(root.left) + size(root.right);
        return root;
    }

    // Count nodes with values in [lo, hi]
    static int countInRange(Node root, int lo, int hi) {
        if (root == null) return 0;
        if (root.val < lo) return countInRange(root.right, lo, hi);
        if (root.val > hi) return countInRange(root.left, lo, hi);
        return 1 + countInRange(root.left, lo, hi) + countInRange(root.right, lo, hi);
    }

    public static void main(String[] args) {
        Node root = null;
        for (int v : new int[]{10, 5, 15, 3, 7, 12, 18}) root = insert(root, v);
        System.out.println(countInRange(root, 5, 15)); // 5
        System.out.println(countInRange(root, 7, 12)); // 3
    }
}

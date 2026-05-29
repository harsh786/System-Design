public class Problem39_BSTRankQuery {
    // BST with size field for O(h) rank queries
    static class Node { int val, size; Node left, right; Node(int v) { val = v; size = 1; } }

    static int size(Node n) { return n == null ? 0 : n.size; }

    static Node insert(Node root, int val) {
        if (root == null) return new Node(val);
        if (val < root.val) root.left = insert(root.left, val);
        else root.right = insert(root.right, val);
        root.size = 1 + size(root.left) + size(root.right);
        return root;
    }

    // Rank: number of elements < val
    static int rank(Node root, int val) {
        if (root == null) return 0;
        if (val <= root.val) return rank(root.left, val);
        return 1 + size(root.left) + rank(root.right, val);
    }

    public static void main(String[] args) {
        Node root = null;
        for (int v : new int[]{5, 3, 8, 1, 4, 7, 10}) root = insert(root, v);
        System.out.println(rank(root, 6)); // 4
        System.out.println(rank(root, 1)); // 0
        System.out.println(rank(root, 11)); // 7
    }
}

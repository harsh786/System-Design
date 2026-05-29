public class Problem40_BSTSelectKthQuery {
    // Select k-th smallest element using augmented BST
    static class Node { int val, size; Node left, right; Node(int v) { val = v; size = 1; } }
    static int size(Node n) { return n == null ? 0 : n.size; }

    static Node insert(Node root, int val) {
        if (root == null) return new Node(val);
        if (val < root.val) root.left = insert(root.left, val);
        else root.right = insert(root.right, val);
        root.size = 1 + size(root.left) + size(root.right);
        return root;
    }

    // k is 1-based
    static int select(Node root, int k) {
        int leftSize = size(root.left);
        if (k == leftSize + 1) return root.val;
        if (k <= leftSize) return select(root.left, k);
        return select(root.right, k - leftSize - 1);
    }

    public static void main(String[] args) {
        Node root = null;
        for (int v : new int[]{5, 3, 8, 1, 4, 7, 10}) root = insert(root, v);
        System.out.println(select(root, 1)); // 1
        System.out.println(select(root, 4)); // 5
        System.out.println(select(root, 7)); // 10
    }
}

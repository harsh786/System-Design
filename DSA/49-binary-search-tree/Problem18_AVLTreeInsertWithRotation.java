public class Problem18_AVLTreeInsertWithRotation {
    static class Node { int val, height; Node left, right; Node(int v) { val = v; height = 1; } }

    static int height(Node n) { return n == null ? 0 : n.height; }
    static int balance(Node n) { return n == null ? 0 : height(n.left) - height(n.right); }

    static Node rightRotate(Node y) {
        Node x = y.left, t = x.right;
        x.right = y; y.left = t;
        y.height = 1 + Math.max(height(y.left), height(y.right));
        x.height = 1 + Math.max(height(x.left), height(x.right));
        return x;
    }

    static Node leftRotate(Node x) {
        Node y = x.right, t = y.left;
        y.left = x; x.right = t;
        x.height = 1 + Math.max(height(x.left), height(x.right));
        y.height = 1 + Math.max(height(y.left), height(y.right));
        return y;
    }

    static Node insert(Node node, int val) {
        if (node == null) return new Node(val);
        if (val < node.val) node.left = insert(node.left, val);
        else if (val > node.val) node.right = insert(node.right, val);
        else return node;
        node.height = 1 + Math.max(height(node.left), height(node.right));
        int bal = balance(node);
        if (bal > 1 && val < node.left.val) return rightRotate(node);
        if (bal < -1 && val > node.right.val) return leftRotate(node);
        if (bal > 1 && val > node.left.val) { node.left = leftRotate(node.left); return rightRotate(node); }
        if (bal < -1 && val < node.right.val) { node.right = rightRotate(node.right); return leftRotate(node); }
        return node;
    }

    static void inorder(Node n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        Node root = null;
        for (int v : new int[]{10, 20, 30, 40, 50, 25}) root = insert(root, v);
        inorder(root); System.out.println(); // 10 20 25 30 40 50
        System.out.println("Root: " + root.val); // 30 (balanced)
    }
}

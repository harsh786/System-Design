public class Problem19_RedBlackTreeInsert {
    // Conceptual Red-Black Tree insert
    static final boolean RED = true, BLACK = false;
    static class Node {
        int val; Node left, right, parent; boolean color;
        Node(int v) { val = v; color = RED; }
    }

    Node root;

    void insert(int val) {
        Node node = new Node(val);
        root = bstInsert(root, node);
        fixInsert(node);
    }

    Node bstInsert(Node root, Node node) {
        if (root == null) return node;
        if (node.val < root.val) { root.left = bstInsert(root.left, node); root.left.parent = root; }
        else { root.right = bstInsert(root.right, node); root.right.parent = root; }
        return root;
    }

    void fixInsert(Node k) {
        while (k != root && k.parent.color == RED) {
            Node parent = k.parent, grand = parent.parent;
            if (grand == null) break;
            if (parent == grand.left) {
                Node uncle = grand.right;
                if (uncle != null && uncle.color == RED) {
                    parent.color = BLACK; uncle.color = BLACK; grand.color = RED; k = grand;
                } else {
                    if (k == parent.right) { k = parent; leftRotate(k); parent = k.parent; grand = parent.parent; }
                    parent.color = BLACK; grand.color = RED; rightRotate(grand);
                }
            } else {
                Node uncle = grand.left;
                if (uncle != null && uncle.color == RED) {
                    parent.color = BLACK; uncle.color = BLACK; grand.color = RED; k = grand;
                } else {
                    if (k == parent.left) { k = parent; rightRotate(k); parent = k.parent; grand = parent.parent; }
                    parent.color = BLACK; grand.color = RED; leftRotate(grand);
                }
            }
        }
        root.color = BLACK;
    }

    void leftRotate(Node x) {
        Node y = x.right; x.right = y.left;
        if (y.left != null) y.left.parent = x;
        y.parent = x.parent;
        if (x.parent == null) root = y;
        else if (x == x.parent.left) x.parent.left = y;
        else x.parent.right = y;
        y.left = x; x.parent = y;
    }

    void rightRotate(Node y) {
        Node x = y.left; y.left = x.right;
        if (x.right != null) x.right.parent = y;
        x.parent = y.parent;
        if (y.parent == null) root = x;
        else if (y == y.parent.left) y.parent.left = x;
        else y.parent.right = x;
        x.right = y; y.parent = x;
    }

    void inorder(Node n) { if (n != null) { inorder(n.left); System.out.print(n.val + "(" + (n.color ? "R" : "B") + ") "); inorder(n.right); } }

    public static void main(String[] args) {
        Problem19_RedBlackTreeInsert rbt = new Problem19_RedBlackTreeInsert();
        for (int v : new int[]{7, 3, 18, 10, 22, 8, 11, 26}) rbt.insert(v);
        rbt.inorder(rbt.root); System.out.println();
    }
}

public class Problem50_BSTIteratorWithParentPointer {
    static class Node { int val; Node left, right, parent; Node(int v) { val = v; } }

    Node current;

    public Problem50_BSTIteratorWithParentPointer(Node root) {
        current = root;
        if (current != null) while (current.left != null) current = current.left;
    }

    public boolean hasNext() { return current != null; }

    public int next() {
        int val = current.val;
        if (current.right != null) {
            current = current.right;
            while (current.left != null) current = current.left;
        } else {
            while (current.parent != null && current == current.parent.right) current = current.parent;
            current = current.parent;
        }
        return val;
    }

    public static void main(String[] args) {
        Node root = new Node(5);
        root.left = new Node(3); root.left.parent = root;
        root.right = new Node(7); root.right.parent = root;
        root.left.left = new Node(1); root.left.left.parent = root.left;
        root.left.right = new Node(4); root.left.right.parent = root.left;
        root.right.left = new Node(6); root.right.left.parent = root.right;

        Problem50_BSTIteratorWithParentPointer it = new Problem50_BSTIteratorWithParentPointer(root);
        while (it.hasNext()) System.out.print(it.next() + " "); // 1 3 4 5 6 7
        System.out.println();
    }
}

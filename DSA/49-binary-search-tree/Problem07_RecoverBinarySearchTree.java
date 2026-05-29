public class Problem07_RecoverBinarySearchTree {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    static TreeNode first, second, prev;

    public static void recoverTree(TreeNode root) {
        first = second = prev = null;
        inorder(root);
        int tmp = first.val; first.val = second.val; second.val = tmp;
    }

    private static void inorder(TreeNode node) {
        if (node == null) return;
        inorder(node.left);
        if (prev != null && prev.val > node.val) {
            if (first == null) first = prev;
            second = node;
        }
        prev = node;
        inorder(node.right);
    }

    static void print(TreeNode n) { if (n != null) { print(n.left); System.out.print(n.val + " "); print(n.right); } }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(3); root.left.right = new TreeNode(2);
        recoverTree(root);
        print(root); System.out.println(); // 1 2 3
    }
}

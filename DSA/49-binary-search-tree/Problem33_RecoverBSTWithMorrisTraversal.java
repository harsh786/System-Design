public class Problem33_RecoverBSTWithMorrisTraversal {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static void recoverTree(TreeNode root) {
        TreeNode first = null, second = null, prev = null;
        TreeNode cur = root;
        while (cur != null) {
            if (cur.left == null) {
                if (prev != null && prev.val > cur.val) {
                    if (first == null) first = prev;
                    second = cur;
                }
                prev = cur; cur = cur.right;
            } else {
                TreeNode pred = cur.left;
                while (pred.right != null && pred.right != cur) pred = pred.right;
                if (pred.right == null) { pred.right = cur; cur = cur.left; }
                else {
                    pred.right = null;
                    if (prev != null && prev.val > cur.val) {
                        if (first == null) first = prev;
                        second = cur;
                    }
                    prev = cur; cur = cur.right;
                }
            }
        }
        int tmp = first.val; first.val = second.val; second.val = tmp;
    }

    static void inorder(TreeNode n) { if (n != null) { inorder(n.left); System.out.print(n.val + " "); inorder(n.right); } }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3);
        root.left = new TreeNode(1); root.right = new TreeNode(4);
        root.right.left = new TreeNode(2);
        recoverTree(root);
        inorder(root); System.out.println(); // 1 2 3 4
    }
}

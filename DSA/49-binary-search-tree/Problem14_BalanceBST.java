import java.util.*;

public class Problem14_BalanceBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static TreeNode balanceBST(TreeNode root) {
        List<Integer> sorted = new ArrayList<>();
        inorder(root, sorted);
        return build(sorted, 0, sorted.size() - 1);
    }

    private static void inorder(TreeNode n, List<Integer> list) {
        if (n == null) return;
        inorder(n.left, list); list.add(n.val); inorder(n.right, list);
    }

    private static TreeNode build(List<Integer> list, int lo, int hi) {
        if (lo > hi) return null;
        int mid = (lo + hi) / 2;
        TreeNode node = new TreeNode(list.get(mid));
        node.left = build(list, lo, mid - 1);
        node.right = build(list, mid + 1, hi);
        return node;
    }

    static void pre(TreeNode n) { if (n != null) { System.out.print(n.val + " "); pre(n.left); pre(n.right); } }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1);
        root.right = new TreeNode(2); root.right.right = new TreeNode(3);
        root.right.right.right = new TreeNode(4);
        TreeNode balanced = balanceBST(root);
        pre(balanced); System.out.println();
    }
}

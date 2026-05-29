import java.util.*;

public class Problem48_MergeTwoBSTs {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static TreeNode mergeTrees(TreeNode r1, TreeNode r2) {
        List<Integer> l1 = new ArrayList<>(), l2 = new ArrayList<>();
        inorder(r1, l1); inorder(r2, l2);
        List<Integer> merged = new ArrayList<>();
        int i = 0, j = 0;
        while (i < l1.size() && j < l2.size())
            merged.add(l1.get(i) <= l2.get(j) ? l1.get(i++) : l2.get(j++));
        while (i < l1.size()) merged.add(l1.get(i++));
        while (j < l2.size()) merged.add(l2.get(j++));
        return build(merged, 0, merged.size() - 1);
    }

    private static void inorder(TreeNode n, List<Integer> list) {
        if (n == null) return; inorder(n.left, list); list.add(n.val); inorder(n.right, list);
    }

    private static TreeNode build(List<Integer> list, int lo, int hi) {
        if (lo > hi) return null;
        int mid = (lo + hi) / 2;
        TreeNode n = new TreeNode(list.get(mid));
        n.left = build(list, lo, mid - 1); n.right = build(list, mid + 1, hi);
        return n;
    }

    static void print(TreeNode n) { if (n != null) { print(n.left); System.out.print(n.val + " "); print(n.right); } }

    public static void main(String[] args) {
        TreeNode r1 = new TreeNode(3); r1.left = new TreeNode(1); r1.right = new TreeNode(5);
        TreeNode r2 = new TreeNode(4); r2.left = new TreeNode(2); r2.right = new TreeNode(6);
        TreeNode merged = mergeTrees(r1, r2);
        print(merged); System.out.println(); // 1 2 3 4 5 6
    }
}

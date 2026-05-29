import java.util.*;

public class Problem25_AllElementsInTwoBSTs {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static List<Integer> getAllElements(TreeNode root1, TreeNode root2) {
        List<Integer> l1 = new ArrayList<>(), l2 = new ArrayList<>();
        inorder(root1, l1); inorder(root2, l2);
        List<Integer> res = new ArrayList<>();
        int i = 0, j = 0;
        while (i < l1.size() && j < l2.size())
            res.add(l1.get(i) <= l2.get(j) ? l1.get(i++) : l2.get(j++));
        while (i < l1.size()) res.add(l1.get(i++));
        while (j < l2.size()) res.add(l2.get(j++));
        return res;
    }

    private static void inorder(TreeNode n, List<Integer> list) {
        if (n == null) return;
        inorder(n.left, list); list.add(n.val); inorder(n.right, list);
    }

    public static void main(String[] args) {
        TreeNode r1 = new TreeNode(2); r1.left = new TreeNode(1); r1.right = new TreeNode(4);
        TreeNode r2 = new TreeNode(1); r2.left = new TreeNode(0); r2.right = new TreeNode(3);
        System.out.println(getAllElements(r1, r2)); // [0,1,1,2,3,4]
    }
}

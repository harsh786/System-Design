import java.util.*;

public class Problem11_BinaryTreeInorderTraversal {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }
    public static List<Integer> inorderTraversal(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        inorder(root, res);
        return res;
    }
    static void inorder(TreeNode node, List<Integer> res) {
        if (node == null) return;
        inorder(node.left, res); res.add(node.val); inorder(node.right, res);
    }
    public static void main(String[] args) {
        TreeNode root = new TreeNode(1); root.right = new TreeNode(2); root.right.left = new TreeNode(3);
        System.out.println(inorderTraversal(root)); // [1,3,2]
    }
}

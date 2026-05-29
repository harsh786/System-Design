import java.util.*;

public class Problem01_ValidateBST {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public static boolean isValidBST(TreeNode root) {
        return validate(root, Long.MIN_VALUE, Long.MAX_VALUE);
    }

    private static boolean validate(TreeNode node, long min, long max) {
        if (node == null) return true;
        if (node.val <= min || node.val >= max) return false;
        return validate(node.left, min, node.val) && validate(node.right, node.val, max);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(2);
        root.left = new TreeNode(1); root.right = new TreeNode(3);
        System.out.println(isValidBST(root)); // true
        TreeNode bad = new TreeNode(5);
        bad.left = new TreeNode(1); bad.right = new TreeNode(4);
        bad.right.left = new TreeNode(3); bad.right.right = new TreeNode(6);
        System.out.println(isValidBST(bad)); // false
    }
}

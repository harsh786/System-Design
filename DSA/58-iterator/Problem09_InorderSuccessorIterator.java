import java.util.*;

public class Problem09_InorderSuccessorIterator {
    static class TreeNode { int val; TreeNode left, right, parent;
        TreeNode(int v){val=v;}
    }

    // Find inorder successor without full tree traversal
    public static TreeNode inorderSuccessor(TreeNode node) {
        if (node.right != null) {
            node = node.right;
            while (node.left != null) node = node.left;
            return node;
        }
        while (node.parent != null && node.parent.right == node) node = node.parent;
        return node.parent;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(5);
        root.left = new TreeNode(3); root.left.parent = root;
        root.right = new TreeNode(7); root.right.parent = root;
        root.left.left = new TreeNode(2); root.left.left.parent = root.left;
        root.left.right = new TreeNode(4); root.left.right.parent = root.left;
        TreeNode succ = inorderSuccessor(root.left.right); // successor of 4 is 5
        System.out.println(succ != null ? succ.val : "null"); // 5
    }
}

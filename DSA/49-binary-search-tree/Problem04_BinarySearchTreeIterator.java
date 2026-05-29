import java.util.*;

public class Problem04_BinarySearchTreeIterator {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    Deque<TreeNode> stack = new ArrayDeque<>();

    public Problem04_BinarySearchTreeIterator(TreeNode root) { pushLeft(root); }

    private void pushLeft(TreeNode node) {
        while (node != null) { stack.push(node); node = node.left; }
    }

    public int next() {
        TreeNode node = stack.pop();
        pushLeft(node.right);
        return node.val;
    }

    public boolean hasNext() { return !stack.isEmpty(); }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(7);
        root.left = new TreeNode(3); root.right = new TreeNode(15);
        root.right.left = new TreeNode(9); root.right.right = new TreeNode(20);
        Problem04_BinarySearchTreeIterator it = new Problem04_BinarySearchTreeIterator(root);
        while (it.hasNext()) System.out.print(it.next() + " "); // 3 7 9 15 20
        System.out.println();
    }
}

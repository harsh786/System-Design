import java.util.*;

public class Problem03_BinarySearchTreeIterator {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v){val=v;} }

    Deque<TreeNode> stack = new ArrayDeque<>();

    public Problem03_BinarySearchTreeIterator(TreeNode root) { pushLeft(root); }

    void pushLeft(TreeNode node) { while (node != null) { stack.push(node); node = node.left; } }

    public int next() { TreeNode node = stack.pop(); pushLeft(node.right); return node.val; }

    public boolean hasNext() { return !stack.isEmpty(); }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(7);
        root.left = new TreeNode(3); root.right = new TreeNode(15);
        root.right.left = new TreeNode(9); root.right.right = new TreeNode(20);
        Problem03_BinarySearchTreeIterator it = new Problem03_BinarySearchTreeIterator(root);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}

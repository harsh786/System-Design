import java.util.*;

public class Problem41_BinaryTreePreorderIterator implements Iterator<Integer> {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v){val=v;} }
    Deque<TreeNode> stack = new ArrayDeque<>();

    public Problem41_BinaryTreePreorderIterator(TreeNode root) { if(root!=null) stack.push(root); }

    public boolean hasNext() { return !stack.isEmpty(); }
    public Integer next() {
        TreeNode n = stack.pop();
        if (n.right != null) stack.push(n.right);
        if (n.left != null) stack.push(n.left);
        return n.val;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.left = new TreeNode(4); root.left.right = new TreeNode(5);
        Problem41_BinaryTreePreorderIterator it = new Problem41_BinaryTreePreorderIterator(root);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 1 2 4 5 3
    }
}

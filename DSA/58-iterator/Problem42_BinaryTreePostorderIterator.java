import java.util.*;

public class Problem42_BinaryTreePostorderIterator implements Iterator<Integer> {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v){val=v;} }
    Deque<TreeNode> stack = new ArrayDeque<>();
    Deque<Integer> output = new ArrayDeque<>();

    public Problem42_BinaryTreePostorderIterator(TreeNode root) {
        if (root != null) stack.push(root);
        while (!stack.isEmpty()) {
            TreeNode n = stack.pop();
            output.push(n.val);
            if (n.left != null) stack.push(n.left);
            if (n.right != null) stack.push(n.right);
        }
    }

    public boolean hasNext() { return !output.isEmpty(); }
    public Integer next() { return output.pop(); }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(1);
        root.left = new TreeNode(2); root.right = new TreeNode(3);
        root.left.left = new TreeNode(4); root.left.right = new TreeNode(5);
        Problem42_BinaryTreePostorderIterator it = new Problem42_BinaryTreePostorderIterator(root);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 4 5 2 3 1
    }
}

import java.util.*;

public class Problem40_BinaryTreeInorderIterator implements Iterator<Integer> {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v){val=v;} }
    Deque<TreeNode> stack = new ArrayDeque<>();

    public Problem40_BinaryTreeInorderIterator(TreeNode root) { pushLeft(root); }
    void pushLeft(TreeNode n) { while(n!=null){stack.push(n);n=n.left;} }

    public boolean hasNext() { return !stack.isEmpty(); }
    public Integer next() { TreeNode n = stack.pop(); pushLeft(n.right); return n.val; }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(4);
        root.left = new TreeNode(2); root.right = new TreeNode(6);
        root.left.left = new TreeNode(1); root.left.right = new TreeNode(3);
        Problem40_BinaryTreeInorderIterator it = new Problem40_BinaryTreeInorderIterator(root);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 1 2 3 4 6
    }
}

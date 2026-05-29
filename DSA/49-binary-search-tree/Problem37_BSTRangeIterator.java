import java.util.*;

public class Problem37_BSTRangeIterator {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    // Iterator that only yields values in [lo, hi]
    Deque<TreeNode> stack = new ArrayDeque<>();
    int hi;

    public Problem37_BSTRangeIterator(TreeNode root, int lo, int hi) {
        this.hi = hi;
        pushLeft(root, lo);
    }

    private void pushLeft(TreeNode node, int lo) {
        while (node != null) {
            if (node.val >= lo) { stack.push(node); node = node.left; }
            else node = node.right;
        }
    }

    public boolean hasNext() { return !stack.isEmpty() && stack.peek().val <= hi; }

    public int next() {
        TreeNode node = stack.pop();
        TreeNode r = node.right;
        while (r != null) { stack.push(r); r = r.left; }
        return node.val;
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(7);
        root.left = new TreeNode(3); root.right = new TreeNode(15);
        root.left.left = new TreeNode(1); root.left.right = new TreeNode(5);
        root.right.left = new TreeNode(9); root.right.right = new TreeNode(20);
        Problem37_BSTRangeIterator it = new Problem37_BSTRangeIterator(root, 4, 16);
        while (it.hasNext()) System.out.print(it.next() + " "); // 5 7 9 15
        System.out.println();
    }
}

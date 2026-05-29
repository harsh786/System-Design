import java.util.*;

public class Problem36_ClosestBSTValueII {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    // Find k values closest to target in BST
    public static List<Integer> closestKValues(TreeNode root, double target, int k) {
        Deque<Integer> deque = new ArrayDeque<>();
        inorder(root, deque);
        while (deque.size() > k) {
            if (Math.abs(deque.peekFirst() - target) > Math.abs(deque.peekLast() - target))
                deque.pollFirst();
            else deque.pollLast();
        }
        return new ArrayList<>(deque);
    }

    private static void inorder(TreeNode n, Deque<Integer> d) {
        if (n == null) return;
        inorder(n.left, d); d.add(n.val); inorder(n.right, d);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(4);
        root.left = new TreeNode(2); root.right = new TreeNode(5);
        root.left.left = new TreeNode(1); root.left.right = new TreeNode(3);
        System.out.println(closestKValues(root, 3.714286, 2)); // [3,4]
    }
}

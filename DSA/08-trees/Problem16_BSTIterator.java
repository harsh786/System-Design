import java.util.*;
/**
 * Problem 16: Binary Search Tree Iterator (LeetCode 173)
 * 
 * Approach: Controlled inorder traversal using stack. Push all left nodes.
 * On next(), pop and push right subtree's lefts.
 * Time: O(1) amortized per next/hasNext, Space: O(h)
 * 
 * Production Analogy: Database cursor over a B-tree index - fetches next row on demand
 * without loading entire result set into memory.
 */
public class Problem16_BSTIterator {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static class BSTIterator {
        private Deque<TreeNode> stack = new ArrayDeque<>();

        public BSTIterator(TreeNode root) {
            pushLeft(root);
        }

        public int next() {
            TreeNode node = stack.pop();
            pushLeft(node.right);
            return node.val;
        }

        public boolean hasNext() {
            return !stack.isEmpty();
        }

        private void pushLeft(TreeNode node) {
            while (node != null) { stack.push(node); node = node.left; }
        }
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(7, new TreeNode(3), new TreeNode(15, new TreeNode(9), new TreeNode(20)));
        BSTIterator it = new BSTIterator(root);
        System.out.println(it.next());    // 3
        System.out.println(it.next());    // 7
        System.out.println(it.hasNext()); // true
        System.out.println(it.next());    // 9
        System.out.println(it.hasNext()); // true
        System.out.println(it.next());    // 15
        System.out.println(it.hasNext()); // true
        System.out.println(it.next());    // 20
        System.out.println(it.hasNext()); // false
    }
}

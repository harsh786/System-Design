import java.util.*;

/**
 * Problem 33: Binary Search Tree Iterator (LeetCode 173)
 * 
 * Implement in-order iterator for BST with O(h) memory.
 * 
 * Approach: Use stack for controlled in-order traversal. Push all left children
 * initially, then on next() pop node, push right child's left spine.
 * 
 * Time Complexity: O(1) amortized per next()
 * Space Complexity: O(h) where h = tree height
 * 
 * Production Analogy: Like database cursor implementation for index scans -
 * traverses B-tree nodes lazily, holding only path from root to current position.
 */
public class Problem33_BinarySearchTreeIterator {

    static class TreeNode {
        int val; TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    static class BSTIterator {
        Deque<TreeNode> stack = new ArrayDeque<>();

        public BSTIterator(TreeNode root) { pushLeft(root); }

        private void pushLeft(TreeNode node) {
            while (node != null) { stack.push(node); node = node.left; }
        }

        public int next() {
            TreeNode node = stack.pop();
            pushLeft(node.right);
            return node.val;
        }

        public boolean hasNext() { return !stack.isEmpty(); }
    }

    public static void main(String[] args) {
        //       7
        //      / \
        //     3   15
        //         / \
        //        9   20
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

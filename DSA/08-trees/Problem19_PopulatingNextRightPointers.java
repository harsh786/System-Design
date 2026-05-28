import java.util.*;
/**
 * Problem 19: Populating Next Right Pointers in Each Node (LeetCode 116/117)
 * 
 * Approach: BFS level-order, link nodes within each level.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Linking sibling pods in a Kubernetes namespace for peer discovery.
 */
public class Problem19_PopulatingNextRightPointers {
    static class TreeNode {
        int val;
        TreeNode left, right, next;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static TreeNode connect(TreeNode root) {
        if (root == null) return null;
        Queue<TreeNode> queue = new LinkedList<>();
        queue.offer(root);
        while (!queue.isEmpty()) {
            int size = queue.size();
            for (int i = 0; i < size; i++) {
                TreeNode node = queue.poll();
                node.next = (i < size - 1) ? queue.peek() : null;
                if (node.left != null) queue.offer(node.left);
                if (node.right != null) queue.offer(node.right);
            }
        }
        return root;
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)),
                                      new TreeNode(3, new TreeNode(6), new TreeNode(7)));
        connect(t1);
        System.out.println("Root.next: " + t1.next); // null
        System.out.println("2.next: " + t1.left.next.val); // 3
        System.out.println("4.next: " + t1.left.left.next.val); // 5
        System.out.println("5.next: " + t1.left.right.next.val); // 6

        System.out.println("Null test: " + connect(null)); // null
    }
}

import java.util.*;

/**
 * Problem: N-ary Tree Level Order Traversal (LeetCode 429)
 * Approach: BFS with queue processing each level
 * Time: O(N), Space: O(N)
 * Production Analogy: Level-by-level traversal of multi-child organizational hierarchy
 */
public class Problem47_NaryTreeLevelOrder {
    static class Node { int val; List<Node> children; Node(int v) { val = v; children = new ArrayList<>(); } }

    public List<List<Integer>> levelOrder(Node root) {
        List<List<Integer>> res = new ArrayList<>();
        if (root == null) return res;
        Queue<Node> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            int size = q.size();
            List<Integer> level = new ArrayList<>();
            for (int i = 0; i < size; i++) {
                Node node = q.poll();
                level.add(node.val);
                for (Node child : node.children) q.offer(child);
            }
            res.add(level);
        }
        return res;
    }

    public static void main(String[] args) {
        Node root = new Node(1);
        Node c1 = new Node(3), c2 = new Node(2), c3 = new Node(4);
        root.children.addAll(Arrays.asList(c1, c2, c3));
        c1.children.addAll(Arrays.asList(new Node(5), new Node(6)));
        System.out.println(new Problem47_NaryTreeLevelOrder().levelOrder(root));
    }
}

import java.util.*;

public class Problem32_NAryTreeLevelOrderTraversal {
    static class Node { int val; List<Node> children; Node(int v) { val = v; children = new ArrayList<>(); } }
    public static List<List<Integer>> levelOrder(Node root) {
        List<List<Integer>> res = new ArrayList<>();
        if (root == null) return res;
        Queue<Node> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            List<Integer> level = new ArrayList<>();
            for (int sz = q.size(); sz > 0; sz--) {
                Node n = q.poll(); level.add(n.val);
                for (Node c : n.children) q.offer(c);
            }
            res.add(level);
        }
        return res;
    }
    public static void main(String[] args) {
        Node root = new Node(1);
        root.children.add(new Node(3)); root.children.add(new Node(2)); root.children.add(new Node(4));
        root.children.get(0).children.add(new Node(5)); root.children.get(0).children.add(new Node(6));
        System.out.println(levelOrder(root));
    }
}

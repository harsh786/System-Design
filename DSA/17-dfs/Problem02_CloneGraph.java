import java.util.*;

/**
 * Problem: Clone Graph (LeetCode 133)
 * Approach: DFS with HashMap to track cloned nodes, avoiding cycles
 * Time: O(V+E), Space: O(V)
 * Production Analogy: Deep copying a service mesh topology for blue-green deployment
 */
public class Problem02_CloneGraph {
    static class Node {
        public int val;
        public List<Node> neighbors;
        Node(int v) { val = v; neighbors = new ArrayList<>(); }
    }

    Map<Node, Node> visited = new HashMap<>();

    public Node cloneGraph(Node node) {
        if (node == null) return null;
        if (visited.containsKey(node)) return visited.get(node);
        Node clone = new Node(node.val);
        visited.put(node, clone);
        for (Node neighbor : node.neighbors) {
            clone.neighbors.add(cloneGraph(neighbor));
        }
        return clone;
    }

    public static void main(String[] args) {
        Node n1 = new Node(1), n2 = new Node(2), n3 = new Node(3), n4 = new Node(4);
        n1.neighbors.addAll(Arrays.asList(n2, n4));
        n2.neighbors.addAll(Arrays.asList(n1, n3));
        n3.neighbors.addAll(Arrays.asList(n2, n4));
        n4.neighbors.addAll(Arrays.asList(n1, n3));
        Node clone = new Problem02_CloneGraph().cloneGraph(n1);
        System.out.println("Cloned node val: " + clone.val + ", neighbors: " + clone.neighbors.size());
    }
}

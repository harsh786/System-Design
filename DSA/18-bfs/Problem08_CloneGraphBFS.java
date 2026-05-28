import java.util.*;

/**
 * Problem: Clone Graph BFS (LeetCode 133)
 * Approach: BFS with HashMap mapping original to clone nodes
 * Time: O(V+E), Space: O(V)
 * Production Analogy: Iterative deep copy of service topology for canary deployments
 */
public class Problem08_CloneGraphBFS {
    static class Node {
        public int val; public List<Node> neighbors;
        Node(int v) { val = v; neighbors = new ArrayList<>(); }
    }

    public Node cloneGraph(Node node) {
        if (node == null) return null;
        Map<Node, Node> map = new HashMap<>();
        Queue<Node> q = new LinkedList<>();
        map.put(node, new Node(node.val));
        q.offer(node);
        while (!q.isEmpty()) {
            Node curr = q.poll();
            for (Node neighbor : curr.neighbors) {
                if (!map.containsKey(neighbor)) {
                    map.put(neighbor, new Node(neighbor.val));
                    q.offer(neighbor);
                }
                map.get(curr).neighbors.add(map.get(neighbor));
            }
        }
        return map.get(node);
    }

    public static void main(String[] args) {
        Node n1 = new Node(1), n2 = new Node(2), n3 = new Node(3);
        n1.neighbors.addAll(Arrays.asList(n2, n3)); n2.neighbors.add(n1); n3.neighbors.add(n1);
        Node clone = new Problem08_CloneGraphBFS().cloneGraph(n1);
        System.out.println("Clone val: " + clone.val + " neighbors: " + clone.neighbors.size());
    }
}

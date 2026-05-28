import java.util.*;

/**
 * Problem 1: Clone Graph (LeetCode 133)
 * 
 * Approach: BFS/DFS with HashMap to track visited nodes and their clones.
 * Time: O(V + E), Space: O(V)
 * 
 * Production Analogy: Cloning a microservice dependency graph for staging environment.
 * Each service (node) has dependencies (neighbors) that must be deep-copied.
 */
public class Problem01_CloneGraph {
    
    static class Node {
        public int val;
        public List<Node> neighbors;
        public Node(int val) { this.val = val; this.neighbors = new ArrayList<>(); }
    }
    
    public Node cloneGraph(Node node) {
        if (node == null) return null;
        Map<Node, Node> visited = new HashMap<>();
        Queue<Node> queue = new LinkedList<>();
        visited.put(node, new Node(node.val));
        queue.offer(node);
        while (!queue.isEmpty()) {
            Node curr = queue.poll();
            for (Node neighbor : curr.neighbors) {
                if (!visited.containsKey(neighbor)) {
                    visited.put(neighbor, new Node(neighbor.val));
                    queue.offer(neighbor);
                }
                visited.get(curr).neighbors.add(visited.get(neighbor));
            }
        }
        return visited.get(node);
    }
    
    public static void main(String[] args) {
        Problem01_CloneGraph sol = new Problem01_CloneGraph();
        
        // Test 1: 4-node cycle graph 1-2-3-4-1
        Node n1 = new Node(1), n2 = new Node(2), n3 = new Node(3), n4 = new Node(4);
        n1.neighbors.addAll(Arrays.asList(n2, n4));
        n2.neighbors.addAll(Arrays.asList(n1, n3));
        n3.neighbors.addAll(Arrays.asList(n2, n4));
        n4.neighbors.addAll(Arrays.asList(n1, n3));
        Node clone = sol.cloneGraph(n1);
        System.out.println("Test 1 - Clone val: " + clone.val + ", neighbors: " + clone.neighbors.size()); // 1, 2
        System.out.println("Test 1 - Is deep copy: " + (clone != n1)); // true
        
        // Test 2: Single node
        Node single = new Node(1);
        Node cloneSingle = sol.cloneGraph(single);
        System.out.println("Test 2 - Single node clone: " + cloneSingle.val + ", neighbors: " + cloneSingle.neighbors.size());
        
        // Test 3: Null
        System.out.println("Test 3 - Null: " + (sol.cloneGraph(null) == null));
    }
}

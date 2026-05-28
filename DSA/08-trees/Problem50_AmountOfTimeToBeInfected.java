import java.util.*;
/**
 * Problem 50: Amount of Time for Binary Tree to Be Infected (LeetCode 2385)
 * 
 * Approach: Build adjacency graph from tree, then BFS from start node counting levels.
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Calculating blast radius time - how long until a cascading failure
 * propagates through the entire service dependency graph.
 */
public class Problem50_AmountOfTimeToBeInfected {
    static class TreeNode {
        int val;
        TreeNode left, right;
        TreeNode(int v) { val = v; }
        TreeNode(int v, TreeNode l, TreeNode r) { val = v; left = l; right = r; }
    }

    public static int amountOfTime(TreeNode root, int start) {
        Map<Integer, List<Integer>> graph = new HashMap<>();
        buildGraph(root, -1, graph);
        
        Queue<Integer> queue = new LinkedList<>();
        Set<Integer> visited = new HashSet<>();
        queue.offer(start);
        visited.add(start);
        int time = -1;
        while (!queue.isEmpty()) {
            int size = queue.size();
            time++;
            for (int i = 0; i < size; i++) {
                int node = queue.poll();
                for (int neighbor : graph.getOrDefault(node, new ArrayList<>())) {
                    if (!visited.contains(neighbor)) {
                        visited.add(neighbor);
                        queue.offer(neighbor);
                    }
                }
            }
        }
        return time;
    }

    private static void buildGraph(TreeNode node, int parent, Map<Integer, List<Integer>> graph) {
        if (node == null) return;
        graph.computeIfAbsent(node.val, k -> new ArrayList<>());
        if (parent != -1) {
            graph.get(node.val).add(parent);
            graph.get(parent).add(node.val);
        }
        buildGraph(node.left, node.val, graph);
        buildGraph(node.right, node.val, graph);
    }

    public static void main(String[] args) {
        TreeNode t1 = new TreeNode(1, new TreeNode(5, null, new TreeNode(4, new TreeNode(9), new TreeNode(2))),
                new TreeNode(3, new TreeNode(10), new TreeNode(6)));
        System.out.println("Test 1 (start=3): " + amountOfTime(t1, 3)); // 4

        TreeNode t2 = new TreeNode(1);
        System.out.println("Test 2 (single): " + amountOfTime(t2, 1)); // 0

        TreeNode t3 = new TreeNode(1, new TreeNode(2), new TreeNode(3));
        System.out.println("Test 3 (start=2): " + amountOfTime(t3, 2)); // 2
    }
}

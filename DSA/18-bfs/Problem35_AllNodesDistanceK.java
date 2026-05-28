import java.util.*;

/**
 * Problem: All Nodes Distance K in Binary Tree (LeetCode 863)
 * Approach: Convert tree to undirected graph, then BFS from target for K steps
 * Time: O(N), Space: O(N)
 * Production Analogy: Finding all services within K hops of a failing node for blast radius
 */
public class Problem35_AllNodesDistanceK {
    static class TreeNode { int val; TreeNode left, right; TreeNode(int v) { val = v; } }

    public List<Integer> distanceK(TreeNode root, TreeNode target, int k) {
        Map<TreeNode, List<TreeNode>> graph = new HashMap<>();
        buildGraph(root, null, graph);
        Queue<TreeNode> q = new LinkedList<>();
        Set<TreeNode> visited = new HashSet<>();
        q.offer(target); visited.add(target);
        int dist = 0;
        while (!q.isEmpty()) {
            if (dist == k) { List<Integer> res = new ArrayList<>(); for (TreeNode n : q) res.add(n.val); return res; }
            int size = q.size(); dist++;
            for (int i = 0; i < size; i++) {
                TreeNode node = q.poll();
                for (TreeNode next : graph.getOrDefault(node, Collections.emptyList()))
                    if (visited.add(next)) q.offer(next);
            }
        }
        return new ArrayList<>();
    }

    private void buildGraph(TreeNode node, TreeNode parent, Map<TreeNode, List<TreeNode>> graph) {
        if (node == null) return;
        graph.computeIfAbsent(node, k -> new ArrayList<>());
        if (parent != null) { graph.get(node).add(parent); graph.get(parent).add(node); }
        buildGraph(node.left, node, graph);
        buildGraph(node.right, node, graph);
    }

    public static void main(String[] args) {
        TreeNode root = new TreeNode(3); root.left = new TreeNode(5); root.right = new TreeNode(1);
        root.left.left = new TreeNode(6); root.left.right = new TreeNode(2);
        System.out.println(new Problem35_AllNodesDistanceK().distanceK(root, root.left, 2));
    }
}

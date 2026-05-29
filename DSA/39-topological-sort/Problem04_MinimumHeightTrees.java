import java.util.*;

/**
 * Problem: Minimum Height Trees
 * Find all roots that give minimum height trees.
 *
 * Approach: Iteratively remove leaf nodes (degree 1) until 1-2 nodes remain.
 * This is essentially reverse topological sort on an undirected tree.
 *
 * Time Complexity: O(V)
 * Space Complexity: O(V)
 *
 * Production Analogy: Finding optimal leader nodes in a distributed network to minimize
 * maximum communication hops.
 */
public class Problem04_MinimumHeightTrees {

    public List<Integer> findMinHeightTrees(int n, int[][] edges) {
        if (n == 1) return Collections.singletonList(0);

        List<Set<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new HashSet<>());
        for (int[] e : edges) {
            graph.get(e[0]).add(e[1]);
            graph.get(e[1]).add(e[0]);
        }

        Queue<Integer> leaves = new LinkedList<>();
        for (int i = 0; i < n; i++)
            if (graph.get(i).size() == 1) leaves.offer(i);

        int remaining = n;
        while (remaining > 2) {
            int size = leaves.size();
            remaining -= size;
            Queue<Integer> newLeaves = new LinkedList<>();
            for (int i = 0; i < size; i++) {
                int leaf = leaves.poll();
                int neighbor = graph.get(leaf).iterator().next();
                graph.get(neighbor).remove(leaf);
                if (graph.get(neighbor).size() == 1) newLeaves.offer(neighbor);
            }
            leaves = newLeaves;
        }
        return new ArrayList<>(leaves);
    }

    public static void main(String[] args) {
        Problem04_MinimumHeightTrees solver = new Problem04_MinimumHeightTrees();
        System.out.println(solver.findMinHeightTrees(4, new int[][]{{1,0},{1,2},{1,3}}));
    }
}

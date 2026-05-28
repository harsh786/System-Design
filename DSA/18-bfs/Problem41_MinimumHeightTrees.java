import java.util.*;

/**
 * Problem: Minimum Height Trees (LeetCode 310)
 * Approach: BFS topological - repeatedly remove leaf nodes until 1-2 remain (centroids)
 * Time: O(N), Space: O(N)
 * Production Analogy: Finding optimal root/leader nodes in a distributed network
 */
public class Problem41_MinimumHeightTrees {
    public List<Integer> findMinHeightTrees(int n, int[][] edges) {
        if (n == 1) return Arrays.asList(0);
        List<Set<Integer>> graph = new ArrayList<>();
        for (int i = 0; i < n; i++) graph.add(new HashSet<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); graph.get(e[1]).add(e[0]); }
        Queue<Integer> leaves = new LinkedList<>();
        for (int i = 0; i < n; i++) if (graph.get(i).size() == 1) leaves.offer(i);
        int remaining = n;
        while (remaining > 2) {
            int size = leaves.size(); remaining -= size;
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
        System.out.println(new Problem41_MinimumHeightTrees().findMinHeightTrees(6, new int[][]{{3,0},{3,1},{3,2},{3,4},{5,4}})); // [3,4]
    }
}

import java.util.*;

/**
 * Problem 22: Minimum Height Trees (LeetCode 310)
 * 
 * Approach: Iteratively remove leaf nodes (degree 1) until 1-2 nodes remain. These are MHT roots.
 * Time: O(V), Space: O(V)
 * 
 * Production Analogy: Finding optimal root/leader node in a cluster to minimize max communication hops.
 */
public class Problem22_MinimumHeightTrees {
    
    public List<Integer> findMinHeightTrees(int n, int[][] edges) {
        if (n == 1) return Collections.singletonList(0);
        Set<Integer>[] adj = new Set[n];
        for (int i = 0; i < n; i++) adj[i] = new HashSet<>();
        for (int[] e : edges) { adj[e[0]].add(e[1]); adj[e[1]].add(e[0]); }
        
        Queue<Integer> leaves = new LinkedList<>();
        for (int i = 0; i < n; i++) if (adj[i].size() == 1) leaves.offer(i);
        int remaining = n;
        while (remaining > 2) {
            int size = leaves.size();
            remaining -= size;
            for (int i = 0; i < size; i++) {
                int leaf = leaves.poll();
                int neighbor = adj[leaf].iterator().next();
                adj[neighbor].remove(leaf);
                if (adj[neighbor].size() == 1) leaves.offer(neighbor);
            }
        }
        return new ArrayList<>(leaves);
    }
    
    public static void main(String[] args) {
        Problem22_MinimumHeightTrees sol = new Problem22_MinimumHeightTrees();
        System.out.println(sol.findMinHeightTrees(4, new int[][]{{1,0},{1,2},{1,3}})); // [1]
        System.out.println(sol.findMinHeightTrees(6, new int[][]{{3,0},{3,1},{3,2},{3,4},{5,4}})); // [3,4]
        System.out.println(sol.findMinHeightTrees(1, new int[][]{})); // [0]
    }
}

import java.util.*;

/**
 * Problem 47: Topological Sort (Kahn's Algorithm)
 * 
 * Approach: BFS-based. Start with in-degree 0 nodes, remove them and reduce neighbors' in-degrees.
 * Time: O(V + E), Space: O(V + E)
 * 
 * Production Analogy: Determining correct startup order for interdependent microservices.
 */
public class Problem47_TopologicalSort {
    
    public List<Integer> topologicalSort(int n, int[][] edges) {
        List<Integer>[] adj = new List[n];
        int[] indegree = new int[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int[] e : edges) { adj[e[0]].add(e[1]); indegree[e[1]]++; }
        
        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (indegree[i] == 0) q.offer(i);
        List<Integer> result = new ArrayList<>();
        while (!q.isEmpty()) {
            int node = q.poll();
            result.add(node);
            for (int next : adj[node]) if (--indegree[next] == 0) q.offer(next);
        }
        return result.size() == n ? result : Collections.emptyList(); // empty if cycle
    }
    
    public static void main(String[] args) {
        Problem47_TopologicalSort sol = new Problem47_TopologicalSort();
        System.out.println(sol.topologicalSort(6, new int[][]{{5,2},{5,0},{4,0},{4,1},{2,3},{3,1}})); 
        System.out.println(sol.topologicalSort(3, new int[][]{{0,1},{1,2},{2,0}})); // [] cycle
        System.out.println(sol.topologicalSort(4, new int[][]{{0,1},{0,2},{1,3},{2,3}}));
    }
}

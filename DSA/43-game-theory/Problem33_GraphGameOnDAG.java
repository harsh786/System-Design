import java.util.*;

public class Problem33_GraphGameOnDAG {
    // Game on DAG: Token on a node. Players move token along directed edge. Can't move = loses.
    // Compute Grundy number for each node using topological order.
    
    public int[] computeGrundy(int n, int[][] edges) {
        List<List<Integer>> adj = new ArrayList<>();
        int[] indegree = new int[n];
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        // We need reverse topo: process sinks first
        List<List<Integer>> radj = new ArrayList<>();
        for (int i = 0; i < n; i++) radj.add(new ArrayList<>());
        int[] outdegree = new int[n];
        for (int[] e : edges) {
            adj.get(e[0]).add(e[1]);
            radj.get(e[1]).add(e[0]);
            outdegree[e[0]]++;
        }
        
        int[] grundy = new int[n];
        boolean[] computed = new boolean[n];
        Queue<Integer> queue = new LinkedList<>();
        for (int i = 0; i < n; i++) if (outdegree[i] == 0) { queue.add(i); computed[i] = true; }
        
        while (!queue.isEmpty()) {
            int u = queue.poll();
            // grundy[u] = mex of grundy of successors
            Set<Integer> reachable = new HashSet<>();
            for (int v : adj.get(u)) reachable.add(grundy[v]);
            int mex = 0;
            while (reachable.contains(mex)) mex++;
            grundy[u] = mex;
            for (int v : radj.get(u)) {
                outdegree[v]--;
                if (outdegree[v] == 0) { queue.add(v); computed[v] = true; }
            }
        }
        return grundy;
    }
    
    public static void main(String[] args) {
        Problem33_GraphGameOnDAG sol = new Problem33_GraphGameOnDAG();
        // DAG: 0->1, 0->2, 1->3, 2->3
        int[] grundy = sol.computeGrundy(4, new int[][]{{0,1},{0,2},{1,3},{2,3}});
        System.out.println(Arrays.toString(grundy)); // node 3=0, node1=1, node2=1, node0=mex{1,1}=0
    }
}

import java.util.*;

/**
 * Problem: All Ancestors of a Node in DAG
 *
 * Approach: Topological sort, propagate ancestor sets forward
 *
 * Time Complexity: O(V^2 + E)
 * Space Complexity: O(V^2)
 *
 * Production Analogy: Computing full dependency trees for vulnerability scanning.
 */
public class Problem20_AllAncestorsOfNodeInDAG {

    public List<List<Integer>> getAncestors(int n, int[][] edges) {
        List<List<Integer>> graph = new ArrayList<>();
        int[] inDeg = new int[n];
        for (int i = 0; i < n; i++) graph.add(new ArrayList<>());
        for (int[] e : edges) { graph.get(e[0]).add(e[1]); inDeg[e[1]]++; }

        Set<Integer>[] ancestors = new TreeSet[n];
        for (int i = 0; i < n; i++) ancestors[i] = new TreeSet<>();

        Queue<Integer> q = new LinkedList<>();
        for (int i = 0; i < n; i++) if (inDeg[i] == 0) q.offer(i);

        while (!q.isEmpty()) {
            int node = q.poll();
            for (int nei : graph.get(node)) {
                ancestors[nei].add(node);
                ancestors[nei].addAll(ancestors[node]);
                if (--inDeg[nei] == 0) q.offer(nei);
            }
        }

        List<List<Integer>> result = new ArrayList<>();
        for (int i = 0; i < n; i++) result.add(new ArrayList<>(ancestors[i]));
        return result;
    }

    public static void main(String[] args) {
        Problem20_AllAncestorsOfNodeInDAG solver = new Problem20_AllAncestorsOfNodeInDAG();
        System.out.println(solver.getAncestors(5, new int[][]{{0,1},{0,2},{1,3},{2,3},{3,4}}));
    }
}

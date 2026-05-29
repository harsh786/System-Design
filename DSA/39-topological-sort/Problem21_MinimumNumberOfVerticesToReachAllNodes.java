import java.util.*;

/**
 * Problem: Minimum Number of Vertices to Reach All Nodes
 *
 * Approach: Return all nodes with in-degree 0 (they can't be reached from others)
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V)
 *
 * Production Analogy: Finding root services that must be started manually (no auto-triggers).
 */
public class Problem21_MinimumNumberOfVerticesToReachAllNodes {

    public List<Integer> findSmallestSetOfVertices(int n, List<List<Integer>> edges) {
        boolean[] hasIncoming = new boolean[n];
        for (List<Integer> e : edges) hasIncoming[e.get(1)] = true;

        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++) if (!hasIncoming[i]) result.add(i);
        return result;
    }

    public static void main(String[] args) {
        Problem21_MinimumNumberOfVerticesToReachAllNodes solver = new Problem21_MinimumNumberOfVerticesToReachAllNodes();
        List<List<Integer>> edges = Arrays.asList(Arrays.asList(0,1),Arrays.asList(0,2),Arrays.asList(2,5),Arrays.asList(3,4),Arrays.asList(4,2));
        System.out.println(solver.findSmallestSetOfVertices(6, edges)); // [0,3]
    }
}

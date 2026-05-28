import java.util.*;

/**
 * Problem 36: Minimum Number of Vertices to Reach All Nodes (LeetCode 1557)
 * 
 * Approach: Nodes with in-degree 0 must be in the answer (they can't be reached from anywhere else).
 * Time: O(V + E), Space: O(V)
 * 
 * Production Analogy: Finding entry-point services that need external triggers (no upstream callers).
 */
public class Problem36_MinimumVertices {
    
    public List<Integer> findSmallestSetOfVertices(int n, List<List<Integer>> edges) {
        boolean[] hasIncoming = new boolean[n];
        for (List<Integer> e : edges) hasIncoming[e.get(1)] = true;
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++) if (!hasIncoming[i]) result.add(i);
        return result;
    }
    
    public static void main(String[] args) {
        Problem36_MinimumVertices sol = new Problem36_MinimumVertices();
        List<List<Integer>> edges = Arrays.asList(Arrays.asList(0,1),Arrays.asList(0,2),Arrays.asList(2,5),Arrays.asList(3,4),Arrays.asList(4,2));
        System.out.println(sol.findSmallestSetOfVertices(6, edges)); // [0, 3]
    }
}

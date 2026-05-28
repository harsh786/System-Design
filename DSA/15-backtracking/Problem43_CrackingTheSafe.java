import java.util.*;

/**
 * Problem 43: Cracking the Safe (LeetCode 753)
 * 
 * Find shortest string that contains every possible n-length password using digits 0..k-1.
 * This is a de Bruijn sequence problem solved via Euler path on graph.
 * 
 * Search Tree:
 * - Build graph where nodes are (n-1)-length strings, edges are n-length strings
 * - Find Euler circuit (visit every edge exactly once)
 * - DFS with Hierholzer's algorithm
 * 
 * Pruning Strategy:
 * - Hierholzer's algorithm is systematic (not really pruning, but efficient traversal)
 * - Track visited edges (passwords)
 * 
 * Time Complexity: O(k^n * n)
 * Space Complexity: O(k^n)
 * 
 * Production Analogy:
 * - Minimizing probe sequences in testing: covering all k^n test inputs with minimum overhead.
 */
public class Problem43_CrackingTheSafe {

    public String crackSafe(int n, int k) {
        if (n == 1) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < k; i++) sb.append(i);
            return sb.toString();
        }
        Set<String> visited = new HashSet<>();
        StringBuilder result = new StringBuilder();
        String start = String.join("", Collections.nCopies(n - 1, "0"));
        dfs(start, k, n, visited, result);
        result.append(start);
        return result.toString();
    }

    private void dfs(String node, int k, int n, Set<String> visited, StringBuilder result) {
        for (int i = 0; i < k; i++) {
            String edge = node + i;
            if (visited.add(edge)) {
                dfs(edge.substring(1), k, n, visited, result);
                result.append(i);
            }
        }
    }

    public static void main(String[] args) {
        Problem43_CrackingTheSafe sol = new Problem43_CrackingTheSafe();

        String res1 = sol.crackSafe(2, 2);
        System.out.println(res1 + " (length=" + res1.length() + ")"); // length 5, e.g. "00110"

        String res2 = sol.crackSafe(1, 2);
        System.out.println(res2); // "01" or "10"

        String res3 = sol.crackSafe(2, 3);
        System.out.println(res3 + " (length=" + res3.length() + ")"); // length 10
    }
}

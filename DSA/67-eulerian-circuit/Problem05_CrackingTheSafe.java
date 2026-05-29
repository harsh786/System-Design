import java.util.*;

/**
 * Problem 5: Cracking the Safe (LeetCode 753)
 * 
 * A password lock has n digits, each from 0 to k-1.
 * Find a string of minimum length that contains all k^n possible passwords as substrings.
 * 
 * This is a De Bruijn sequence problem solved via Eulerian circuit:
 * - Create a graph where each node is a (n-1)-digit string
 * - Edge from node "abc" to "bcd" labeled 'd' represents password "abcd"
 * - An Eulerian circuit visits all edges = all passwords
 * 
 * The graph has k^(n-1) nodes, each with k outgoing and k incoming edges.
 * Every node has in-degree = out-degree = k, so Eulerian circuit exists.
 * 
 * Result length: k^n + n - 1
 */
public class Problem05_CrackingTheSafe {

    public static String crackSafe(int n, int k) {
        if (n == 1) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < k; i++) sb.append(i);
            return sb.toString();
        }
        
        // Start node: "000...0" (n-1 zeros)
        StringBuilder startNode = new StringBuilder();
        for (int i = 0; i < n - 1; i++) startNode.append('0');
        
        Set<String> visited = new HashSet<>();
        StringBuilder result = new StringBuilder();
        result.append(startNode);
        
        dfs(startNode.toString(), k, visited, result);
        
        return result.toString();
    }

    private static void dfs(String node, int k, Set<String> visited, StringBuilder result) {
        for (int i = 0; i < k; i++) {
            String edge = node + i;
            if (!visited.contains(edge)) {
                visited.add(edge);
                // Next node is last (n-1) chars of edge
                String nextNode = edge.substring(1);
                dfs(nextNode, k, visited, result);
                result.append(i);
            }
        }
    }

    public static void main(String[] args) {
        // n=2, k=2: passwords are "00", "01", "10", "11"
        String result1 = crackSafe(2, 2);
        System.out.println("n=2, k=2: " + result1);
        System.out.println("Length: " + result1.length() + " (optimal: " + ((int)Math.pow(2,2)+2-1) + ")");
        // Verify all passwords present
        Set<String> found = new HashSet<>();
        for (int i = 0; i <= result1.length() - 2; i++) {
            found.add(result1.substring(i, i + 2));
        }
        System.out.println("Contains all passwords: " + (found.size() == 4));

        // n=3, k=2: passwords are "000" through "111"
        String result2 = crackSafe(3, 2);
        System.out.println("\nn=3, k=2: " + result2);
        System.out.println("Length: " + result2.length() + " (optimal: " + ((int)Math.pow(2,3)+3-1) + ")");
        
        // n=2, k=3
        String result3 = crackSafe(2, 3);
        System.out.println("\nn=2, k=3: " + result3);
        System.out.println("Length: " + result3.length() + " (optimal: " + ((int)Math.pow(3,2)+2-1) + ")");
    }
}

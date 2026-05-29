import java.util.*;

/**
 * Problem 8: De Bruijn Sequence
 * 
 * A De Bruijn sequence B(k,n) is a cyclic sequence where every possible
 * subsequence of length n over an alphabet of size k appears exactly once.
 * 
 * Length of sequence: k^n (cyclic) or k^n + n - 1 (linear)
 * 
 * Construction via Eulerian circuit:
 * - Nodes: all (n-1)-length strings over alphabet
 * - Edge from "abc" to "bcd" labeled with character 'd'
 * - Eulerian circuit gives the De Bruijn sequence
 * 
 * Applications: DNA sequencing, lock cracking, pseudo-random sequences
 */
public class Problem08_DeBruijnSequence {

    /**
     * Generate De Bruijn sequence B(k, n) using Hierholzer's
     */
    public static String deBruijn(int k, int n) {
        if (n == 1) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < k; i++) sb.append(i);
            return sb.toString();
        }
        
        // Nodes are (n-1)-digit numbers in base k
        int numNodes = (int) Math.pow(k, n - 1);
        // Each node has k outgoing edges (append digit 0..k-1)
        
        int[] visited = new int[numNodes]; // Track next edge to try
        StringBuilder result = new StringBuilder();
        
        // DFS-based Hierholzer's
        dfs(0, k, n, numNodes, visited, result);
        
        // Add starting node prefix
        StringBuilder prefix = new StringBuilder();
        for (int i = 0; i < n - 1; i++) prefix.append('0');
        
        return result.toString() + prefix.toString();
    }

    private static void dfs(int node, int k, int n, int numNodes, int[] visited, StringBuilder result) {
        while (visited[node] < k) {
            int digit = visited[node]++;
            int nextNode = (node * k + digit) % numNodes;
            dfs(nextNode, k, n, numNodes, visited, result);
            result.append(digit);
        }
    }

    /**
     * Verify De Bruijn sequence contains all k^n substrings
     */
    public static boolean verify(String seq, int k, int n) {
        Set<String> expected = new HashSet<>();
        generateAll("", k, n, expected);
        
        Set<String> found = new HashSet<>();
        // Treat as cyclic
        String cyclic = seq + seq.substring(0, n - 1);
        for (int i = 0; i <= cyclic.length() - n; i++) {
            found.add(cyclic.substring(i, i + n));
        }
        return found.equals(expected);
    }

    private static void generateAll(String prefix, int k, int n, Set<String> result) {
        if (prefix.length() == n) { result.add(prefix); return; }
        for (int i = 0; i < k; i++) generateAll(prefix + i, k, n, result);
    }

    public static void main(String[] args) {
        System.out.println("De Bruijn Sequences:\n");
        
        int[][] tests = {{2, 2}, {2, 3}, {2, 4}, {3, 2}};
        for (int[] test : tests) {
            int k = test[0], n = test[1];
            String seq = deBruijn(k, n);
            boolean valid = verify(seq, k, n);
            System.out.printf("B(%d,%d): length=%d (expected %d), valid=%b%n", 
                k, n, seq.length(), (int)Math.pow(k,n) + n - 1, valid);
            if (seq.length() <= 30) System.out.println("  Sequence: " + seq);
            System.out.println();
        }
    }
}

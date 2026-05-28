import java.util.*;

/**
 * Problem 20: Number of Connected Components (LeetCode 323)
 * 
 * Approach: Union-Find or DFS/BFS. Count distinct roots.
 * Time: O(V + E), Space: O(V)
 * 
 * Production Analogy: Counting isolated network partitions in a distributed system.
 */
public class Problem20_NumberOfConnectedComponents {
    
    public int countComponents(int n, int[][] edges) {
        int[] parent = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        int components = n;
        for (int[] e : edges) {
            int p1 = find(parent, e[0]), p2 = find(parent, e[1]);
            if (p1 != p2) { parent[p1] = p2; components--; }
        }
        return components;
    }
    
    int find(int[] parent, int x) { return parent[x] == x ? x : (parent[x] = find(parent, parent[x])); }
    
    public static void main(String[] args) {
        Problem20_NumberOfConnectedComponents sol = new Problem20_NumberOfConnectedComponents();
        System.out.println(sol.countComponents(5, new int[][]{{0,1},{1,2},{3,4}})); // 2
        System.out.println(sol.countComponents(5, new int[][]{{0,1},{1,2},{2,3},{3,4}})); // 1
        System.out.println(sol.countComponents(4, new int[][]{})); // 4
    }
}

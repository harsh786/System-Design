import java.util.*;

public class Problem13_InteractiveBipartition {
    // Determine if graph is bipartite using edge queries
    static boolean[][] adj = {
        {false,true,false,true},
        {true,false,true,false},
        {false,true,false,true},
        {true,false,true,false}
    };
    
    static boolean hasEdge(int u, int v) { return adj[u][v]; }
    
    static boolean isBipartite(int n) {
        int[] color = new int[n];
        Arrays.fill(color, -1);
        for (int start = 0; start < n; start++) {
            if (color[start] != -1) continue;
            Queue<Integer> q = new LinkedList<>();
            q.add(start); color[start] = 0;
            while (!q.isEmpty()) {
                int u = q.poll();
                for (int v = 0; v < n; v++) {
                    if (v == u || !hasEdge(u, v)) continue;
                    if (color[v] == -1) { color[v] = 1 - color[u]; q.add(v); }
                    else if (color[v] == color[u]) return false;
                }
            }
        }
        return true;
    }
    
    public static void main(String[] args) {
        System.out.println("Is bipartite: " + isBipartite(4)); // true
    }
}

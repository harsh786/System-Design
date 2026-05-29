import java.util.*;

public class Problem26_InteractiveGraphDiameter {
    static List<List<Integer>> adj = Arrays.asList(
        Arrays.asList(1,2), Arrays.asList(0,3,4), Arrays.asList(0,5),
        Arrays.asList(1), Arrays.asList(1), Arrays.asList(2,6), Arrays.asList(5));
    
    static List<Integer> getNeighbors(int u) { return adj.get(u); }
    
    static int bfsFarthest(int start, int n) {
        int[] dist = new int[n]; Arrays.fill(dist, -1);
        Queue<Integer> q = new LinkedList<>(); q.add(start); dist[start] = 0;
        int farthest = start;
        while (!q.isEmpty()) {
            int u = q.poll();
            for (int v : getNeighbors(u)) {
                if (dist[v] == -1) { dist[v] = dist[u] + 1; q.add(v); farthest = v; }
            }
        }
        return farthest;
    }
    
    static int diameter(int n) {
        int u = bfsFarthest(0, n);
        int v = bfsFarthest(u, n);
        // compute distance u to v
        int[] dist = new int[n]; Arrays.fill(dist, -1);
        Queue<Integer> q = new LinkedList<>(); q.add(u); dist[u] = 0;
        while (!q.isEmpty()) {
            int x = q.poll();
            for (int nb : getNeighbors(x)) if (dist[nb]==-1) { dist[nb]=dist[x]+1; q.add(nb); }
        }
        return dist[v];
    }
    
    public static void main(String[] args) {
        System.out.println("Diameter: " + diameter(7));
    }
}

import java.util.*;

public class Problem27_InteractiveShortestPath {
    static int[][] graph = {{0,4,0,0,0},{4,0,8,0,0},{0,8,0,7,0},{0,0,7,0,9},{0,0,0,9,0}};
    
    static int getWeight(int u, int v) { return graph[u][v]; }
    static int n = 5;
    
    static int[] dijkstra(int src) {
        int[] dist = new int[n]; Arrays.fill(dist, Integer.MAX_VALUE); dist[src] = 0;
        boolean[] visited = new boolean[n];
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b)->a[1]-b[1]);
        pq.offer(new int[]{src, 0});
        while (!pq.isEmpty()) {
            int[] cur = pq.poll(); int u = cur[0];
            if (visited[u]) continue; visited[u] = true;
            for (int v = 0; v < n; v++) {
                int w = getWeight(u, v);
                if (w > 0 && dist[u] + w < dist[v]) { dist[v] = dist[u] + w; pq.offer(new int[]{v, dist[v]}); }
            }
        }
        return dist;
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(dijkstra(0)));
    }
}

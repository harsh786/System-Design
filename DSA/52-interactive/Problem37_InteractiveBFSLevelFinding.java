import java.util.*;

public class Problem37_InteractiveBFSLevelFinding {
    static List<List<Integer>> adj = Arrays.asList(
        Arrays.asList(1,2), Arrays.asList(0,3), Arrays.asList(0,4), Arrays.asList(1), Arrays.asList(2,5), Arrays.asList(4));
    
    static List<Integer> getNeighbors(int u) { return adj.get(u); }
    
    static int findLevel(int start, int target, int n) {
        int[] dist = new int[n]; Arrays.fill(dist, -1); dist[start] = 0;
        Queue<Integer> q = new LinkedList<>(); q.add(start);
        while (!q.isEmpty()) {
            int u = q.poll();
            if (u == target) return dist[u];
            for (int v : getNeighbors(u)) if (dist[v]==-1) { dist[v]=dist[u]+1; q.add(v); }
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Level of node 5 from 0: " + findLevel(0, 5, 6)); // 3
    }
}

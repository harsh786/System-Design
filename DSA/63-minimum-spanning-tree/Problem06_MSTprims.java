import java.util.*;

public class Problem06_MSTprims {
    public int primMST(int n, int[][] edges) {
        List<int[]>[] adj = new List[n];
        for (int i = 0; i < n; i++) adj[i] = new ArrayList<>();
        for (int[] e : edges) { adj[e[0]].add(new int[]{e[1],e[2]}); adj[e[1]].add(new int[]{e[0],e[2]}); }
        boolean[] visited = new boolean[n];
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b)->a[1]-b[1]);
        pq.offer(new int[]{0,0});
        int cost = 0, count = 0;
        while (count < n) {
            int[] cur = pq.poll();
            if (visited[cur[0]]) continue;
            visited[cur[0]] = true; cost += cur[1]; count++;
            for (int[] nei : adj[cur[0]]) if (!visited[nei[0]]) pq.offer(new int[]{nei[0], nei[1]});
        }
        return cost;
    }

    public static void main(String[] args) {
        Problem06_MSTprims sol = new Problem06_MSTprims();
        System.out.println(sol.primMST(4, new int[][]{{0,1,1},{0,2,4},{1,2,2},{1,3,5},{2,3,3}})); // 6
    }
}

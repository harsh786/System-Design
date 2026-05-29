import java.util.*;

public class Problem01_MinCostToConnectAllPoints {
    /* Prim's algorithm */
    public int minCostConnectPoints(int[][] points) {
        int n = points.length, cost = 0, edges = 0;
        boolean[] visited = new boolean[n];
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[0]-b[0]);
        pq.offer(new int[]{0, 0});
        while (edges < n) {
            int[] cur = pq.poll();
            if (visited[cur[1]]) continue;
            visited[cur[1]] = true;
            cost += cur[0]; edges++;
            for (int j = 0; j < n; j++) {
                if (!visited[j]) {
                    int d = Math.abs(points[cur[1]][0]-points[j][0]) + Math.abs(points[cur[1]][1]-points[j][1]);
                    pq.offer(new int[]{d, j});
                }
            }
        }
        return cost;
    }

    public static void main(String[] args) {
        Problem01_MinCostToConnectAllPoints sol = new Problem01_MinCostToConnectAllPoints();
        System.out.println(sol.minCostConnectPoints(new int[][]{{0,0},{2,2},{3,10},{5,2},{7,0}})); // 20
    }
}

import java.util.*;

/**
 * Problem: The Maze II (LeetCode 505)
 * Approach: BFS/Dijkstra - ball rolls until wall, track shortest distance
 * Time: O(M*N*max(M,N)), Space: O(M*N)
 * Production Analogy: Finding minimum-latency path where packets travel full segments
 */
public class Problem28_TheMazeII {
    public int shortestDistance(int[][] maze, int[] start, int[] destination) {
        int m = maze.length, n = maze[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[start[0]][start[1]] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a,b) -> a[2]-b[2]);
        pq.offer(new int[]{start[0], start[1], 0});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!pq.isEmpty()) {
            int[] curr = pq.poll();
            if (curr[2] > dist[curr[0]][curr[1]]) continue;
            for (int[] d : dirs) {
                int r = curr[0], c = curr[1], steps = 0;
                while (r+d[0]>=0 && r+d[0]<m && c+d[1]>=0 && c+d[1]<n && maze[r+d[0]][c+d[1]]==0) {
                    r+=d[0]; c+=d[1]; steps++;
                }
                if (curr[2]+steps < dist[r][c]) {
                    dist[r][c] = curr[2]+steps;
                    pq.offer(new int[]{r, c, dist[r][c]});
                }
            }
        }
        return dist[destination[0]][destination[1]] == Integer.MAX_VALUE ? -1 : dist[destination[0]][destination[1]];
    }

    public static void main(String[] args) {
        int[][] maze = {{0,0,1,0,0},{0,0,0,0,0},{0,0,0,1,0},{1,1,0,1,1},{0,0,0,0,0}};
        System.out.println(new Problem28_TheMazeII().shortestDistance(maze, new int[]{0,4}, new int[]{4,4})); // 12
    }
}

import java.util.*;

/**
 * Problem: The Maze II
 * Ball rolls until hitting wall. Find shortest distance to destination.
 *
 * Approach: Dijkstra where each state is a cell, edge weight = roll distance
 *
 * Time Complexity: O(m*n*max(m,n)*log(m*n))
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Routing with momentum - finding shortest path with inertia constraints.
 */
public class Problem17_TheMazeII {

    public int shortestDistance(int[][] maze, int[] start, int[] dest) {
        int m = maze.length, n = maze[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[start[0]][start[1]] = 0;

        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{start[0], start[1], 0});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!pq.isEmpty()) {
            int[] cur = pq.poll();
            if (cur[2] > dist[cur[0]][cur[1]]) continue;
            for (int[] d : dirs) {
                int r = cur[0], c = cur[1], steps = 0;
                while (r+d[0]>=0 && r+d[0]<m && c+d[1]>=0 && c+d[1]<n && maze[r+d[0]][c+d[1]]==0) {
                    r += d[0]; c += d[1]; steps++;
                }
                if (cur[2] + steps < dist[r][c]) {
                    dist[r][c] = cur[2] + steps;
                    pq.offer(new int[]{r, c, dist[r][c]});
                }
            }
        }
        return dist[dest[0]][dest[1]] == Integer.MAX_VALUE ? -1 : dist[dest[0]][dest[1]];
    }

    public static void main(String[] args) {
        Problem17_TheMazeII solver = new Problem17_TheMazeII();
        int[][] maze = {{0,0,1,0,0},{0,0,0,0,0},{0,0,0,1,0},{1,1,0,1,1},{0,0,0,0,0}};
        System.out.println(solver.shortestDistance(maze, new int[]{0,4}, new int[]{4,4})); // 12
    }
}

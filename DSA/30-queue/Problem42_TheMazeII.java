import java.util.*;

public class Problem42_TheMazeII {
    public static int shortestDistance(int[][] maze, int[] start, int[] dest) {
        int m = maze.length, n = maze[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[start[0]][start[1]] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[2] - b[2]);
        pq.offer(new int[]{start[0], start[1], 0});
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!pq.isEmpty()) {
            int[] c = pq.poll();
            if (c[2] > dist[c[0]][c[1]]) continue;
            for (int[] d : dirs) {
                int r = c[0], col = c[1], steps = 0;
                while (r+d[0] >= 0 && r+d[0] < m && col+d[1] >= 0 && col+d[1] < n && maze[r+d[0]][col+d[1]] == 0) { r += d[0]; col += d[1]; steps++; }
                if (c[2] + steps < dist[r][col]) { dist[r][col] = c[2] + steps; pq.offer(new int[]{r, col, dist[r][col]}); }
            }
        }
        return dist[dest[0]][dest[1]] == Integer.MAX_VALUE ? -1 : dist[dest[0]][dest[1]];
    }
    public static void main(String[] args) {
        int[][] maze = {{0,0,1,0,0},{0,0,0,0,0},{0,0,0,1,0},{1,1,0,1,1},{0,0,0,0,0}};
        System.out.println(shortestDistance(maze, new int[]{0,4}, new int[]{4,4})); // 12
    }
}

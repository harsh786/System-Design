import java.util.*;

/**
 * Problem 14: Shortest Path in Binary Matrix
 * 
 * Find shortest path from top-left to bottom-right in binary grid (0=open, 1=blocked).
 * Can move in 8 directions.
 *
 * Approach: BFS from (0,0). BFS guarantees shortest path in unweighted graph.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m * n)
 *
 * Production Analogy: Shortest network route finding in a grid topology,
 * like finding minimum hop count between two nodes in a mesh network.
 */
public class Problem14_ShortestPathInBinaryMatrix {

    public static int shortestPathBinaryMatrix(int[][] grid) {
        int n = grid.length;
        if (grid[0][0] == 1 || grid[n-1][n-1] == 1) return -1;
        Queue<int[]> queue = new LinkedList<>();
        queue.offer(new int[]{0, 0, 1});
        grid[0][0] = 1;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0},{1,1},{1,-1},{-1,1},{-1,-1}};
        while (!queue.isEmpty()) {
            int[] cur = queue.poll();
            if (cur[0] == n-1 && cur[1] == n-1) return cur[2];
            for (int[] d : dirs) {
                int ni = cur[0]+d[0], nj = cur[1]+d[1];
                if (ni >= 0 && ni < n && nj >= 0 && nj < n && grid[ni][nj] == 0) {
                    grid[ni][nj] = 1;
                    queue.offer(new int[]{ni, nj, cur[2]+1});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + shortestPathBinaryMatrix(new int[][]{{0,1},{1,0}})); // 2
        System.out.println("Test 2: " + shortestPathBinaryMatrix(new int[][]{{0,0,0},{1,1,0},{1,1,0}})); // 4
        System.out.println("Test 3: " + shortestPathBinaryMatrix(new int[][]{{1,0},{0,0}})); // -1
    }
}

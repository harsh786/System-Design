import java.util.*;

/**
 * Problem 39: Count Servers that Communicate
 * 
 * Servers on grid communicate if in same row or column with another server.
 * Count servers that can communicate.
 *
 * Approach: Count servers per row and per column. A server communicates if its
 * row count > 1 or column count > 1.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(m + n)
 *
 * Production Analogy: Finding servers on shared network segments (same VLAN/subnet)
 * that can directly communicate without routing.
 */
public class Problem39_CountServersThatCommunicate {

    public static int countServers(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[] rowCount = new int[m], colCount = new int[n];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 1) { rowCount[i]++; colCount[j]++; }
        int count = 0;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 1 && (rowCount[i] > 1 || colCount[j] > 1)) count++;
        return count;
    }

    public static void main(String[] args) {
        System.out.println("Test 1: " + countServers(new int[][]{{1,0},{0,1}})); // 0
        System.out.println("Test 2: " + countServers(new int[][]{{1,0},{1,1}})); // 3
        System.out.println("Test 3: " + countServers(new int[][]{{1,1,0,0},{0,0,1,0},{0,0,1,0},{0,0,0,1}})); // 4
    }
}

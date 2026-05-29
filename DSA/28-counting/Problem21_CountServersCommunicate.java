/**
 * Problem: Count Servers that Communicate (LeetCode 1267)
 * Approach: Count servers per row and column
 * Complexity: O(m*n) time, O(m+n) space
 * Production Analogy: Identifying connected nodes in network topology
 */
public class Problem21_CountServersCommunicate {
    public int countServers(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[] rowCount = new int[m], colCount = new int[n];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j]==1) { rowCount[i]++; colCount[j]++; }
        int count = 0;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j]==1 && (rowCount[i]>1 || colCount[j]>1)) count++;
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem21_CountServersCommunicate().countServers(
            new int[][]{{1,0},{1,1}})); // 3
    }
}

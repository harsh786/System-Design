/**
 * Problem 50: Stamping the Grid (LeetCode 2132)
 * 
 * Pattern: 2D prefix sum to check if a rectangle is all zeros (stampable),
 * then 2D difference array to mark stamped regions, then verify all zeros are covered.
 * 
 * Steps:
 * 1. 2D prefix sum of grid to quickly check if any sub-rectangle contains occupied cells
 * 2. Mark all valid stamp positions using a 2D difference array
 * 3. 2D prefix sum of difference array to get coverage count per cell
 * 4. Verify every empty cell has coverage > 0
 * 
 * Time: O(m*n), Space: O(m*n)
 * 
 * Production Analogy: Tile-based resource allocation in data centers—checking if
 * contiguous rack units are free to place a multi-unit server, then validating
 * all empty slots are covered by at least one placement.
 */
public class Problem50_StampingTheGrid {

    public static boolean possibleToStamp(int[][] grid, int stampHeight, int stampWidth) {
        int m = grid.length, n = grid[0].length;

        // Step 1: 2D prefix sum of grid (count of occupied cells)
        int[][] prefix = new int[m + 1][n + 1];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                prefix[i + 1][j + 1] = grid[i][j] + prefix[i][j + 1] + prefix[i + 1][j] - prefix[i][j];

        // Step 2: 2D difference array for stamp placements
        int[][] diff = new int[m + 2][n + 2];
        for (int i = 0; i <= m - stampHeight; i++) {
            for (int j = 0; j <= n - stampWidth; j++) {
                int r2 = i + stampHeight - 1, c2 = j + stampWidth - 1;
                // Check if sub-rectangle is all zeros
                int occupied = prefix[r2 + 1][c2 + 1] - prefix[i][c2 + 1] - prefix[r2 + 1][j] + prefix[i][j];
                if (occupied == 0) {
                    // Mark stamp placement in diff array (1-indexed offset for safety)
                    diff[i + 1][j + 1]++;
                    diff[i + 1][c2 + 2]--;
                    diff[r2 + 2][j + 1]--;
                    diff[r2 + 2][c2 + 2]++;
                }
            }
        }

        // Step 3: 2D prefix sum of diff to get coverage
        int[][] coverage = new int[m + 2][n + 2];
        for (int i = 1; i <= m; i++)
            for (int j = 1; j <= n; j++)
                coverage[i][j] = diff[i][j] + coverage[i - 1][j] + coverage[i][j - 1] - coverage[i - 1][j - 1];

        // Step 4: Check all empty cells are covered
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (grid[i][j] == 0 && coverage[i + 1][j + 1] == 0)
                    return false;
        return true;
    }

    public static void main(String[] args) {
        assert possibleToStamp(new int[][]{
            {1, 0, 0, 0},
            {1, 0, 0, 0},
            {1, 0, 0, 0},
            {1, 0, 0, 0},
            {1, 0, 0, 0}
        }, 4, 3) == true;

        assert possibleToStamp(new int[][]{
            {1, 0, 0, 0},
            {0, 1, 0, 0},
            {0, 0, 1, 0},
            {0, 0, 0, 1}
        }, 2, 2) == false;

        assert possibleToStamp(new int[][]{
            {0, 0},
            {0, 0}
        }, 2, 2) == true;

        assert possibleToStamp(new int[][]{
            {1, 1},
            {1, 1}
        }, 1, 1) == true; // no empty cells to cover

        System.out.println("All tests passed!");
    }
}

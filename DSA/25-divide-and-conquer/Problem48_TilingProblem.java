/**
 * Problem 48: Tiling Problem (L-shaped Trominoes)
 * Fill a 2^n x 2^n board (with one missing square) using L-shaped trominoes.
 * 
 * D&C Approach:
 * - DIVIDE: Split board into 4 quadrants of size 2^(n-1) x 2^(n-1)
 * - CONQUER: One quadrant has the missing tile. Place an L-tromino at the
 *   junction of the other 3 quadrants (creating a "missing" tile in each).
 * - Recurse on all 4 quadrants (each now has exactly one missing tile)
 * 
 * Time: O(4^n) = O(n^2) where n = side length (fills every cell)
 * Space: O(n^2) for the board + O(log n) recursion
 * 
 * Production Analogy:
 * - Recursive space filling (fractal generation)
 * - Divide-and-conquer resource allocation in grid computing
 * - Hierarchical decomposition in parallel computing
 */
public class Problem48_TilingProblem {

    private static int tileId = 0;
    private static int[][] board;

    public static int[][] tile(int size, int missRow, int missCol) {
        board = new int[size][size];
        tileId = 0;
        board[missRow][missCol] = -1; // Mark missing tile
        fillTiles(0, 0, size, missRow, missCol);
        return board;
    }

    private static void fillTiles(int row, int col, int size, int missRow, int missCol) {
        if (size == 1) return;
        
        int half = size / 2;
        tileId++;
        int currentTile = tileId;
        
        // Determine which quadrant has the missing tile
        // For other 3 quadrants, place L-tromino at their corners meeting center
        
        // Top-left quadrant
        if (missRow < row + half && missCol < col + half) {
            fillTiles(row, col, half, missRow, missCol);
        } else {
            board[row + half - 1][col + half - 1] = currentTile;
            fillTiles(row, col, half, row + half - 1, col + half - 1);
        }
        
        // Top-right quadrant
        if (missRow < row + half && missCol >= col + half) {
            fillTiles(row, col + half, half, missRow, missCol);
        } else {
            board[row + half - 1][col + half] = currentTile;
            fillTiles(row, col + half, half, row + half - 1, col + half);
        }
        
        // Bottom-left quadrant
        if (missRow >= row + half && missCol < col + half) {
            fillTiles(row + half, col, half, missRow, missCol);
        } else {
            board[row + half][col + half - 1] = currentTile;
            fillTiles(row + half, col, half, row + half, col + half - 1);
        }
        
        // Bottom-right quadrant
        if (missRow >= row + half && missCol >= col + half) {
            fillTiles(row + half, col + half, half, missRow, missCol);
        } else {
            board[row + half][col + half] = currentTile;
            fillTiles(row + half, col + half, half, row + half, col + half);
        }
    }

    public static void main(String[] args) {
        int[][] result = tile(4, 0, 0);
        System.out.println("4x4 board with missing tile at (0,0):");
        for (int[] row : result) {
            for (int cell : row) System.out.printf("%3d", cell);
            System.out.println();
        }
        
        System.out.println("\n2x2 board with missing tile at (1,1):");
        int[][] r2 = tile(2, 1, 1);
        for (int[] row : r2) {
            for (int cell : row) System.out.printf("%3d", cell);
            System.out.println();
        }
    }
}

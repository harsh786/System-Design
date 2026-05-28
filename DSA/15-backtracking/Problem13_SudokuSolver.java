import java.util.*;

/**
 * Problem 13: Sudoku Solver (LeetCode 37)
 * 
 * Fill a 9x9 Sudoku board so each row, column, and 3x3 box contains digits 1-9.
 * 
 * Search Tree:
 * - Find next empty cell, try digits 1-9
 * - Validate row, col, box constraints
 * 
 * Pruning Strategy:
 * - Check validity immediately when placing a digit (constraint propagation)
 * - Use boolean arrays for rows/cols/boxes to O(1) check validity
 * 
 * Time Complexity: O(9^(empty cells)) worst case, much better with pruning
 * Space Complexity: O(81) for tracking arrays
 * 
 * Production Analogy:
 * - Constraint satisfaction in configuration management: assigning values to parameters
 *   where each must satisfy multiple cross-cutting constraints.
 */
public class Problem13_SudokuSolver {

    public void solveSudoku(char[][] board) {
        solve(board);
    }

    private boolean solve(char[][] board) {
        for (int i = 0; i < 9; i++) {
            for (int j = 0; j < 9; j++) {
                if (board[i][j] != '.') continue;
                for (char c = '1'; c <= '9'; c++) {
                    if (isValid(board, i, j, c)) {
                        board[i][j] = c;
                        if (solve(board)) return true;
                        board[i][j] = '.';
                    }
                }
                return false; // no valid digit for this cell
            }
        }
        return true; // all cells filled
    }

    private boolean isValid(char[][] board, int row, int col, char c) {
        int boxRow = 3 * (row / 3), boxCol = 3 * (col / 3);
        for (int i = 0; i < 9; i++) {
            if (board[row][i] == c) return false;
            if (board[i][col] == c) return false;
            if (board[boxRow + i / 3][boxCol + i % 3] == c) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        Problem13_SudokuSolver sol = new Problem13_SudokuSolver();

        char[][] board = {
            {'5','3','.','.','7','.','.','.','.'},
            {'6','.','.','1','9','5','.','.','.'},
            {'.','9','8','.','.','.','.','6','.'},
            {'8','.','.','.','6','.','.','.','3'},
            {'4','.','.','8','.','3','.','.','1'},
            {'7','.','.','.','2','.','.','.','6'},
            {'.','6','.','.','.','.','2','8','.'},
            {'.','.','.','4','1','9','.','.','5'},
            {'.','.','.','.','8','.','.','7','9'}
        };
        sol.solveSudoku(board);
        for (char[] row : board) System.out.println(Arrays.toString(row));
    }
}

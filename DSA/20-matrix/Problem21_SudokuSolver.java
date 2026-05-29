import java.util.*;

/**
 * Problem 21: Sudoku Solver
 * 
 * Solve a Sudoku puzzle by filling empty cells.
 *
 * Approach: Backtracking. Try each number 1-9 in empty cells, validate, recurse.
 *
 * Time Complexity: O(9^(empty cells)) worst case, pruned significantly
 * Space Complexity: O(81) recursion depth
 *
 * Production Analogy: Constraint satisfaction problems in scheduling - assigning
 * resources to slots with mutual exclusion constraints (like shift scheduling).
 */
public class Problem21_SudokuSolver {

    public static void solveSudoku(char[][] board) {
        solve(board);
    }

    private static boolean solve(char[][] board) {
        for (int i = 0; i < 9; i++)
            for (int j = 0; j < 9; j++) {
                if (board[i][j] != '.') continue;
                for (char c = '1'; c <= '9'; c++) {
                    if (isValid(board, i, j, c)) {
                        board[i][j] = c;
                        if (solve(board)) return true;
                        board[i][j] = '.';
                    }
                }
                return false;
            }
        return true;
    }

    private static boolean isValid(char[][] board, int row, int col, char c) {
        for (int i = 0; i < 9; i++) {
            if (board[row][i] == c) return false;
            if (board[i][col] == c) return false;
            if (board[row/3*3 + i/3][col/3*3 + i%3] == c) return false;
        }
        return true;
    }

    public static void main(String[] args) {
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
        solveSudoku(board);
        for (char[] row : board) System.out.println(Arrays.toString(row));
    }
}

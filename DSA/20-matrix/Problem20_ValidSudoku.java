import java.util.*;

/**
 * Problem 20: Valid Sudoku
 * 
 * Determine if a 9x9 Sudoku board is valid (no duplicates in rows, cols, boxes).
 *
 * Approach: Use HashSets or boolean arrays for each row, column, and 3x3 box.
 *
 * Time Complexity: O(81) = O(1)
 * Space Complexity: O(81) = O(1)
 *
 * Production Analogy: Constraint validation in configuration matrices - ensuring
 * no conflicts in resource allocation grids (e.g., no two VMs on same host with same port).
 */
public class Problem20_ValidSudoku {

    public static boolean isValidSudoku(char[][] board) {
        boolean[][] rows = new boolean[9][9], cols = new boolean[9][9], boxes = new boolean[9][9];
        for (int i = 0; i < 9; i++)
            for (int j = 0; j < 9; j++) {
                if (board[i][j] == '.') continue;
                int num = board[i][j] - '1';
                int box = (i/3)*3 + j/3;
                if (rows[i][num] || cols[j][num] || boxes[box][num]) return false;
                rows[i][num] = cols[j][num] = boxes[box][num] = true;
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
        System.out.println("Test 1: " + isValidSudoku(board)); // true

        board[0][0] = '8'; // duplicate in box
        System.out.println("Test 2: " + isValidSudoku(board)); // false
    }
}

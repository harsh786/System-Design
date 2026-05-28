import java.util.*;

/**
 * Problem 29: Valid Sudoku
 * Determine if a 9x9 Sudoku board is valid (no duplicates in rows, cols, boxes).
 *
 * Approach: Use HashSets for each row, column, and 3x3 box.
 *
 * Time Complexity: O(1) - fixed 81 cells
 * Space Complexity: O(1)
 *
 * Production Analogy: Like constraint validation in a distributed config system -
 * ensuring no conflicts across multiple dimensions (row=service, col=region, box=cluster).
 */
public class Problem29_ValidSudoku {
    public boolean isValidSudoku(char[][] board) {
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < 9; i++) {
            for (int j = 0; j < 9; j++) {
                char c = board[i][j];
                if (c == '.') continue;
                if (!seen.add(c + "row" + i) ||
                    !seen.add(c + "col" + j) ||
                    !seen.add(c + "box" + i/3 + j/3))
                    return false;
            }
        }
        return true;
    }

    public static void main(String[] args) {
        Problem29_ValidSudoku sol = new Problem29_ValidSudoku();
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
        System.out.println(sol.isValidSudoku(board)); // true
    }
}

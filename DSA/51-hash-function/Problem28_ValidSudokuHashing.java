import java.util.*;

public class Problem28_ValidSudokuHashing {
    public boolean isValidSudoku(char[][] board) {
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < 9; i++) {
            for (int j = 0; j < 9; j++) {
                char c = board[i][j];
                if (c == '.') continue;
                if (!seen.add(c + "r" + i) || !seen.add(c + "c" + j) || !seen.add(c + "b" + i/3 + j/3))
                    return false;
            }
        }
        return true;
    }

    public static void main(String[] args) {
        Problem28_ValidSudokuHashing sol = new Problem28_ValidSudokuHashing();
        char[][] board = {{'5','3','.','.','7','.','.','.','.'},{'6','.','.','1','9','5','.','.','.'},
            {'.','9','8','.','.','.','.','6','.'},{'8','.','.','.','6','.','.','.','3'},
            {'4','.','.','8','.','3','.','.','1'},{'7','.','.','.','2','.','.','.','6'},
            {'.','6','.','.','.','.','2','8','.'},{'.','.','.','4','1','9','.','.','5'},
            {'.','.','.','.','8','.','.','7','9'}};
        System.out.println(sol.isValidSudoku(board)); // true
    }
}

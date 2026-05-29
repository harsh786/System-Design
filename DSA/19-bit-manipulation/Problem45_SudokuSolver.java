/**
 * Problem 45: Sudoku Solver (Bitmask approach)
 * 
 * Approach: For each row, col, box maintain 9-bit mask of used digits.
 * Available digits at cell = ~(row[r] | col[c] | box[b]) & 0x1FF.
 * Time: O(9^(empty cells)) worst case but pruning helps. Space: O(81)
 * 
 * Production Analogy: Constraint-based resource allocation in multi-dimensional scheduling.
 */
public class Problem45_SudokuSolver {
    private int[] rows = new int[9], cols = new int[9], boxes = new int[9];

    public void solveSudoku(char[][] board) {
        for (int r = 0; r < 9; r++)
            for (int c = 0; c < 9; c++)
                if (board[r][c] != '.') {
                    int bit = 1 << (board[r][c] - '1');
                    rows[r] |= bit; cols[c] |= bit; boxes[r/3*3+c/3] |= bit;
                }
        solve(board, 0);
    }

    private boolean solve(char[][] board, int idx) {
        if (idx == 81) return true;
        int r = idx / 9, c = idx % 9;
        if (board[r][c] != '.') return solve(board, idx + 1);
        int available = ~(rows[r] | cols[c] | boxes[r/3*3+c/3]) & 0x1FF;
        while (available != 0) {
            int bit = available & (-available);
            available &= (available - 1);
            int d = Integer.numberOfTrailingZeros(bit);
            board[r][c] = (char)('1' + d);
            rows[r] |= bit; cols[c] |= bit; boxes[r/3*3+c/3] |= bit;
            if (solve(board, idx + 1)) return true;
            board[r][c] = '.';
            rows[r] ^= bit; cols[c] ^= bit; boxes[r/3*3+c/3] ^= bit;
        }
        return false;
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
        new Problem45_SudokuSolver().solveSudoku(board);
        for (char[] row : board) System.out.println(new String(row));
    }
}

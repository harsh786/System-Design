public class Problem33_SudokuSolver {
    int[] rows = new int[9], cols = new int[9], boxes = new int[9];

    public void solveSudoku(char[][] board) {
        for (int i = 0; i < 9; i++) for (int j = 0; j < 9; j++) if (board[i][j] != '.') {
            int bit = 1 << (board[i][j] - '1');
            rows[i] |= bit; cols[j] |= bit; boxes[i/3*3+j/3] |= bit;
        }
        solve(board, 0);
    }

    private boolean solve(char[][] board, int pos) {
        if (pos == 81) return true;
        int r = pos / 9, c = pos % 9;
        if (board[r][c] != '.') return solve(board, pos + 1);
        int used = rows[r] | cols[c] | boxes[r/3*3+c/3];
        int avail = ~used & 0x1FF;
        while (avail != 0) {
            int bit = avail & -avail; avail ^= bit;
            board[r][c] = (char)('1' + Integer.numberOfTrailingZeros(bit));
            rows[r] |= bit; cols[c] |= bit; boxes[r/3*3+c/3] |= bit;
            if (solve(board, pos + 1)) return true;
            rows[r] ^= bit; cols[c] ^= bit; boxes[r/3*3+c/3] ^= bit;
        }
        board[r][c] = '.';
        return false;
    }

    public static void main(String[] args) {
        char[][] board = {{'5','3','.','.','7','.','.','.','.'},{'6','.','.','1','9','5','.','.','.'},{'.','9','8','.','.','.','.','6','.'},{'8','.','.','.','6','.','.','.','3'},{'4','.','.','8','.','3','.','.','1'},{'7','.','.','.','2','.','.','.','6'},{'.','6','.','.','.','.','2','8','.'},{'.','.','.','4','1','9','.','.','5'},{'.','.','.','.','8','.','.','7','9'}};
        new Problem33_SudokuSolver().solveSudoku(board);
        for (char[] row : board) System.out.println(new String(row));
    }
}

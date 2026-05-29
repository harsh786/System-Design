public class Problem34_SudokuSolver {
    public void solveSudoku(char[][] board) { solve(board, 0); }
    private boolean solve(char[][] board, int pos) {
        if (pos == 81) return true;
        int r = pos/9, c = pos%9;
        if (board[r][c] != '.') return solve(board, pos+1);
        for (char ch = '1'; ch <= '9'; ch++) {
            if (isValid(board,r,c,ch)) { board[r][c]=ch; if (solve(board,pos+1)) return true; board[r][c]='.'; }
        }
        return false;
    }
    private boolean isValid(char[][] board, int r, int c, char ch) {
        for (int i = 0; i < 9; i++) { if (board[r][i]==ch||board[i][c]==ch) return false; if (board[r/3*3+i/3][c/3*3+i%3]==ch) return false; }
        return true;
    }
    public static void main(String[] args) {
        char[][] board = {{'5','3','.','.','7','.','.','.','.'},{'6','.','.','1','9','5','.','.','.'},{'.','9','8','.','.','.','.','6','.'},{'8','.','.','.','6','.','.','.','3'},{'4','.','.','8','.','3','.','.','1'},{'7','.','.','.','2','.','.','.','6'},{'.','6','.','.','.','.','2','8','.'},{'.','.','.','4','1','9','.','.','5'},{'.','.','.','.','8','.','.','7','9'}};
        new Problem34_SudokuSolver().solveSudoku(board);
        for (char[] row : board) System.out.println(new String(row));
    }
}

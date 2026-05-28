/**
 * Problem: Minesweeper (LeetCode 529)
 * Approach: DFS - reveal cells, count adjacent mines, recurse if count is 0
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Cascading health check reveals in monitoring dashboards
 */
public class Problem36_Minesweeper {
    int[][] dirs = {{-1,-1},{-1,0},{-1,1},{0,-1},{0,1},{1,-1},{1,0},{1,1}};

    public char[][] updateBoard(char[][] board, int[] click) {
        int r = click[0], c = click[1];
        if (board[r][c] == 'M') { board[r][c] = 'X'; return board; }
        reveal(board, r, c);
        return board;
    }

    private void reveal(char[][] board, int r, int c) {
        if (r < 0 || r >= board.length || c < 0 || c >= board[0].length || board[r][c] != 'E') return;
        int mines = 0;
        for (int[] d : dirs) {
            int nr = r+d[0], nc = c+d[1];
            if (nr >= 0 && nr < board.length && nc >= 0 && nc < board[0].length && (board[nr][nc] == 'M' || board[nr][nc] == 'X')) mines++;
        }
        if (mines > 0) { board[r][c] = (char)('0' + mines); }
        else { board[r][c] = 'B'; for (int[] d : dirs) reveal(board, r+d[0], c+d[1]); }
    }

    public static void main(String[] args) {
        char[][] board = {{'E','E','E','E','E'},{'E','E','M','E','E'},{'E','E','E','E','E'},{'E','E','E','E','E'}};
        char[][] res = new Problem36_Minesweeper().updateBoard(board, new int[]{3,0});
        for (char[] row : res) System.out.println(java.util.Arrays.toString(row));
    }
}

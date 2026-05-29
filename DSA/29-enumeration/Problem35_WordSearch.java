public class Problem35_WordSearch {
    public boolean exist(char[][] board, String word) {
        int m = board.length, n = board[0].length;
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) if (dfs(board,word,i,j,0)) return true;
        return false;
    }
    private boolean dfs(char[][] board, String word, int r, int c, int idx) {
        if (idx == word.length()) return true;
        if (r<0||r>=board.length||c<0||c>=board[0].length||board[r][c]!=word.charAt(idx)) return false;
        char tmp = board[r][c]; board[r][c]='#';
        boolean found = dfs(board,word,r+1,c,idx+1)||dfs(board,word,r-1,c,idx+1)||dfs(board,word,r,c+1,idx+1)||dfs(board,word,r,c-1,idx+1);
        board[r][c]=tmp; return found;
    }
    public static void main(String[] args) { System.out.println(new Problem35_WordSearch().exist(new char[][]{{'A','B','C','E'},{'S','F','C','S'},{'A','D','E','E'}},"ABCCED")); }
}

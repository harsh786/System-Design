import java.util.*;

public class Problem34_WordSearchIIWithBitmaskVisited {
    // For small grids (<=5x5), use bitmask for visited cells
    public List<String> findWords(char[][] board, String[] words) {
        Set<String> result = new HashSet<>();
        int m = board.length, n = board[0].length;
        for (String word : words) {
            for (int i = 0; i < m && !result.contains(word); i++)
                for (int j = 0; j < n && !result.contains(word); j++)
                    if (board[i][j] == word.charAt(0) && dfs(board, word, 0, i, j, 1 << (i*n+j), m, n))
                        result.add(word);
        }
        return new ArrayList<>(result);
    }

    private boolean dfs(char[][] board, String word, int idx, int r, int c, int visited, int m, int n) {
        if (idx == word.length() - 1) return true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        for (int[] d : dirs) {
            int nr = r+d[0], nc = c+d[1];
            if (nr>=0 && nr<m && nc>=0 && nc<n && (visited&(1<<(nr*n+nc)))==0 && board[nr][nc]==word.charAt(idx+1))
                if (dfs(board, word, idx+1, nr, nc, visited|(1<<(nr*n+nc)), m, n)) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        char[][] board = {{'o','a','a','n'},{'e','t','a','e'},{'i','h','k','r'},{'i','f','l','v'}};
        System.out.println(new Problem34_WordSearchIIWithBitmaskVisited().findWords(board, new String[]{"oath","eat","rain"}));
    }
}

import java.util.*;

/**
 * Problem: N-Queens (LeetCode 51)
 * Approach: DFS backtracking row by row, track columns and diagonals
 * Time: O(N!), Space: O(N)
 * Production Analogy: Resource placement with mutual exclusion constraints (pod anti-affinity)
 */
public class Problem12_NQueens {
    public List<List<String>> solveNQueens(int n) {
        List<List<String>> res = new ArrayList<>();
        dfs(n, 0, new int[n], new boolean[n], new boolean[2*n], new boolean[2*n], res);
        return res;
    }

    private void dfs(int n, int row, int[] queens, boolean[] cols, boolean[] d1, boolean[] d2, List<List<String>> res) {
        if (row == n) {
            List<String> board = new ArrayList<>();
            for (int q : queens) { char[] r = new char[n]; Arrays.fill(r,'.'); r[q]='Q'; board.add(new String(r)); }
            res.add(board); return;
        }
        for (int col = 0; col < n; col++) {
            if (cols[col] || d1[row-col+n] || d2[row+col]) continue;
            queens[row] = col; cols[col] = d1[row-col+n] = d2[row+col] = true;
            dfs(n, row+1, queens, cols, d1, d2, res);
            cols[col] = d1[row-col+n] = d2[row+col] = false;
        }
    }

    public static void main(String[] args) {
        List<List<String>> res = new Problem12_NQueens().solveNQueens(4);
        for (List<String> b : res) { b.forEach(System.out::println); System.out.println(); }
    }
}

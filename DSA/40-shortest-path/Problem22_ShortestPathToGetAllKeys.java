import java.util.*;

/**
 * Problem: Shortest Path to Get All Keys
 *
 * Approach: BFS with state = (row, col, keys_bitmask)
 *
 * Time Complexity: O(m*n*2^k) where k = number of keys
 * Space Complexity: O(m*n*2^k)
 *
 * Production Analogy: Minimum steps to acquire all credentials for a multi-auth system.
 */
public class Problem22_ShortestPathToGetAllKeys {

    public int shortestPathAllKeys(String[] grid) {
        int m = grid.length, n = grid[0].length();
        int startR = 0, startC = 0, totalKeys = 0;
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                char c = grid[i].charAt(j);
                if (c == '@') { startR = i; startC = j; }
                if (c >= 'a' && c <= 'f') totalKeys = Math.max(totalKeys, c - 'a' + 1);
            }

        int target = (1 << totalKeys) - 1;
        boolean[][][] visited = new boolean[m][n][1 << totalKeys];
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{startR, startC, 0, 0});
        visited[startR][startC][0] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};

        while (!q.isEmpty()) {
            int[] cur = q.poll();
            int r = cur[0], c = cur[1], keys = cur[2], steps = cur[3];
            for (int[] d : dirs) {
                int nr = r+d[0], nc = c+d[1], nk = keys;
                if (nr<0||nr>=m||nc<0||nc>=n||grid[nr].charAt(nc)=='#') continue;
                char ch = grid[nr].charAt(nc);
                if (ch>='A'&&ch<='F'&&(keys&(1<<(ch-'A')))==0) continue;
                if (ch>='a'&&ch<='f') nk |= (1<<(ch-'a'));
                if (nk == target) return steps + 1;
                if (!visited[nr][nc][nk]) { visited[nr][nc][nk] = true; q.offer(new int[]{nr,nc,nk,steps+1}); }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem22_ShortestPathToGetAllKeys solver = new Problem22_ShortestPathToGetAllKeys();
        System.out.println(solver.shortestPathAllKeys(new String[]{"@.a..","###.#","b.A.B"})); // 8
    }
}

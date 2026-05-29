import java.util.*;

public class Problem18_BitmaskBFSWithKeys {
    public int shortestPathAllKeys(String[] grid) {
        int m = grid.length, n = grid[0].length(), keys = 0;
        int sr = 0, sc = 0;
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) {
            char c = grid[i].charAt(j);
            if (c == '@') { sr = i; sc = j; }
            if (c >= 'a' && c <= 'f') keys++;
        }
        int full = (1 << keys) - 1;
        boolean[][][] visited = new boolean[m][n][1 << keys];
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{sr, sc, 0, 0});
        visited[sr][sc][0] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cur = q.poll();
            int r = cur[0], c = cur[1], k = cur[2], d = cur[3];
            if (k == full) return d;
            for (int[] dir : dirs) {
                int nr = r + dir[0], nc = c + dir[1], nk = k;
                if (nr < 0 || nr >= m || nc < 0 || nc >= n) continue;
                char ch = grid[nr].charAt(nc);
                if (ch == '#') continue;
                if (ch >= 'A' && ch <= 'F' && (k & (1 << (ch - 'A'))) == 0) continue;
                if (ch >= 'a' && ch <= 'f') nk |= (1 << (ch - 'a'));
                if (!visited[nr][nc][nk]) { visited[nr][nc][nk] = true; q.offer(new int[]{nr, nc, nk, d + 1}); }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(new Problem18_BitmaskBFSWithKeys().shortestPathAllKeys(new String[]{"@.a..","###.#","b.A.B"}));
    }
}

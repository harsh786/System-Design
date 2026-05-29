import java.util.*;

public class Problem25_ShortestPathToGetAllKeys {
    public int shortestPathAllKeys(String[] grid) {
        int m = grid.length, n = grid[0].length(), keys = 0, sr = 0, sc = 0;
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) {
            char c = grid[i].charAt(j);
            if (c == '@') { sr = i; sc = j; }
            if (c >= 'a' && c <= 'f') keys = Math.max(keys, c - 'a' + 1);
        }
        int full = (1 << keys) - 1;
        boolean[][][] vis = new boolean[m][n][1 << keys];
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{sr, sc, 0, 0}); vis[sr][sc][0] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cur = q.poll();
            if (cur[2] == full) return cur[3];
            for (int[] d : dirs) {
                int nr = cur[0]+d[0], nc = cur[1]+d[1], nk = cur[2];
                if (nr<0||nr>=m||nc<0||nc>=n) continue;
                char ch = grid[nr].charAt(nc);
                if (ch == '#') continue;
                if (ch>='A'&&ch<='F'&&(nk&(1<<(ch-'A')))==0) continue;
                if (ch>='a'&&ch<='f') nk|=(1<<(ch-'a'));
                if (!vis[nr][nc][nk]) { vis[nr][nc][nk]=true; q.offer(new int[]{nr,nc,nk,cur[3]+1}); }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(new Problem25_ShortestPathToGetAllKeys().shortestPathAllKeys(new String[]{"@.a..","###.#","b.A.B"}));
    }
}

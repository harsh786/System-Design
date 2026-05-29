import java.util.*;

public class Problem39_ShortestPathToGetAllKeys {
    public static int shortestPathAllKeys(String[] grid) {
        int m = grid.length, n = grid[0].length(), allKeys = 0;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) {
            char c = grid[i].charAt(j);
            if (c == '@') q.offer(new int[]{i, j, 0});
            if (c >= 'a' && c <= 'f') allKeys |= (1 << (c - 'a'));
        }
        Set<String> visited = new HashSet<>();
        visited.add(q.peek()[0] + "," + q.peek()[1] + ",0");
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int steps = 0;
        while (!q.isEmpty()) {
            steps++;
            for (int sz = q.size(); sz > 0; sz--) {
                int[] cur = q.poll();
                for (int[] d : dirs) {
                    int r = cur[0]+d[0], c = cur[1]+d[1], keys = cur[2];
                    if (r < 0 || r >= m || c < 0 || c >= n) continue;
                    char ch = grid[r].charAt(c);
                    if (ch == '#') continue;
                    if (ch >= 'A' && ch <= 'F' && (keys & (1 << (ch - 'A'))) == 0) continue;
                    int newKeys = keys;
                    if (ch >= 'a' && ch <= 'f') newKeys |= (1 << (ch - 'a'));
                    if (newKeys == allKeys) return steps;
                    String state = r + "," + c + "," + newKeys;
                    if (visited.add(state)) q.offer(new int[]{r, c, newKeys});
                }
            }
        }
        return -1;
    }
    public static void main(String[] args) {
        System.out.println(shortestPathAllKeys(new String[]{"@.a..","###.#","b.A.B"})); // 8
    }
}

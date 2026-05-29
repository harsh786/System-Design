import java.util.*;

/**
 * Problem: Cut Off Trees for Golf Event
 * Cut trees in order of height, find min steps.
 *
 * Approach: Sort trees by height, BFS between consecutive trees
 *
 * Time Complexity: O(m^2 * n^2) worst case
 * Space Complexity: O(m*n)
 *
 * Production Analogy: Minimum travel to process ordered tasks at different locations.
 */
public class Problem25_CutOffTreesForGolfEvent {

    public int cutOffTree(List<List<Integer>> forest) {
        List<int[]> trees = new ArrayList<>();
        int m = forest.size(), n = forest.get(0).size();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if (forest.get(i).get(j) > 1) trees.add(new int[]{forest.get(i).get(j), i, j});
        trees.sort((a, b) -> a[0] - b[0]);

        int total = 0, sr = 0, sc = 0;
        for (int[] tree : trees) {
            int dist = bfs(forest, sr, sc, tree[1], tree[2], m, n);
            if (dist == -1) return -1;
            total += dist; sr = tree[1]; sc = tree[2];
        }
        return total;
    }

    private int bfs(List<List<Integer>> forest, int sr, int sc, int tr, int tc, int m, int n) {
        if (sr == tr && sc == tc) return 0;
        boolean[][] visited = new boolean[m][n];
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{sr, sc, 0}); visited[sr][sc] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cur = q.poll();
            for (int[] d : dirs) {
                int nr = cur[0]+d[0], nc = cur[1]+d[1];
                if (nr>=0&&nr<m&&nc>=0&&nc<n&&!visited[nr][nc]&&forest.get(nr).get(nc)>0) {
                    if (nr==tr&&nc==tc) return cur[2]+1;
                    visited[nr][nc] = true; q.offer(new int[]{nr,nc,cur[2]+1});
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem25_CutOffTreesForGolfEvent solver = new Problem25_CutOffTreesForGolfEvent();
        List<List<Integer>> forest = Arrays.asList(Arrays.asList(1,2,3),Arrays.asList(0,0,4),Arrays.asList(7,6,5));
        System.out.println(solver.cutOffTree(forest)); // 6
    }
}

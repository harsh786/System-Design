import java.util.*;

/**
 * Problem: Cut Off Trees for Golf Event (LeetCode 675)
 * Approach: Sort trees by height, BFS between consecutive trees for shortest path
 * Time: O(M^2 * N^2), Space: O(M*N)
 * Production Analogy: Ordered task execution with minimum travel between distributed nodes
 */
public class Problem20_CutOffTreesGolf {
    public int cutOffTree(List<List<Integer>> forest) {
        List<int[]> trees = new ArrayList<>();
        for (int i = 0; i < forest.size(); i++)
            for (int j = 0; j < forest.get(0).size(); j++)
                if (forest.get(i).get(j) > 1) trees.add(new int[]{forest.get(i).get(j), i, j});
        trees.sort((a, b) -> a[0] - b[0]);
        int total = 0, sr = 0, sc = 0;
        for (int[] tree : trees) {
            int dist = bfs(forest, sr, sc, tree[1], tree[2]);
            if (dist == -1) return -1;
            total += dist; sr = tree[1]; sc = tree[2];
        }
        return total;
    }

    private int bfs(List<List<Integer>> forest, int sr, int sc, int tr, int tc) {
        if (sr == tr && sc == tc) return 0;
        int m = forest.size(), n = forest.get(0).size();
        boolean[][] visited = new boolean[m][n];
        Queue<int[]> q = new LinkedList<>();
        q.offer(new int[]{sr, sc}); visited[sr][sc] = true;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        int steps = 0;
        while (!q.isEmpty()) {
            int size = q.size(); steps++;
            for (int i = 0; i < size; i++) {
                int[] cell = q.poll();
                for (int[] d : dirs) {
                    int ni = cell[0]+d[0], nj = cell[1]+d[1];
                    if (ni >= 0 && ni < m && nj >= 0 && nj < n && !visited[ni][nj] && forest.get(ni).get(nj) > 0) {
                        if (ni == tr && nj == tc) return steps;
                        visited[ni][nj] = true; q.offer(new int[]{ni, nj});
                    }
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        List<List<Integer>> forest = Arrays.asList(
            Arrays.asList(1,2,3), Arrays.asList(0,0,4), Arrays.asList(7,6,5));
        System.out.println(new Problem20_CutOffTreesGolf().cutOffTree(forest)); // 6
    }
}

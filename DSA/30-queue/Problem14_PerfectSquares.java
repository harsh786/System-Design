import java.util.*;

public class Problem14_PerfectSquares {
    public static int numSquares(int n) {
        Queue<Integer> q = new LinkedList<>();
        boolean[] visited = new boolean[n+1];
        q.offer(0); visited[0] = true;
        int level = 0;
        while (!q.isEmpty()) {
            level++;
            for (int sz = q.size(); sz > 0; sz--) {
                int cur = q.poll();
                for (int i = 1; i*i + cur <= n; i++) {
                    int next = cur + i*i;
                    if (next == n) return level;
                    if (!visited[next]) { visited[next] = true; q.offer(next); }
                }
            }
        }
        return level;
    }
    public static void main(String[] args) {
        System.out.println(numSquares(12)); // 3
    }
}

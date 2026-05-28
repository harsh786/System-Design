import java.util.*;

/**
 * Problem: Perfect Squares (LeetCode 279)
 * Approach: BFS - each number is a node, subtract perfect squares for edges
 * Time: O(N*sqrt(N)), Space: O(N)
 * Production Analogy: Minimum denominations needed to make change in payment systems
 */
public class Problem15_PerfectSquares {
    public int numSquares(int n) {
        Queue<Integer> q = new LinkedList<>();
        boolean[] visited = new boolean[n + 1];
        q.offer(n); visited[n] = true;
        int level = 0;
        while (!q.isEmpty()) {
            int size = q.size(); level++;
            for (int i = 0; i < size; i++) {
                int curr = q.poll();
                for (int j = 1; j * j <= curr; j++) {
                    int next = curr - j * j;
                    if (next == 0) return level;
                    if (!visited[next]) { visited[next] = true; q.offer(next); }
                }
            }
        }
        return n;
    }

    public static void main(String[] args) {
        System.out.println(new Problem15_PerfectSquares().numSquares(12)); // 3
    }
}

import java.util.*;

/**
 * Problem 14: IPO (LeetCode 502)
 * 
 * Approach: Sort projects by capital requirement. Use max-heap for profits of
 * affordable projects. Greedily pick most profitable affordable project.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Investment portfolio optimization - selecting projects that
 * maximize returns given current available capital constraints.
 */
public class Problem14_IPO {
    
    public int findMaximizedCapital(int k, int w, int[] profits, int[] capital) {
        int n = profits.length;
        int[][] projects = new int[n][2];
        for (int i = 0; i < n; i++) projects[i] = new int[]{capital[i], profits[i]};
        Arrays.sort(projects, (a, b) -> a[0] - b[0]);
        
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        int idx = 0;
        
        for (int i = 0; i < k; i++) {
            while (idx < n && projects[idx][0] <= w) {
                maxHeap.offer(projects[idx][1]);
                idx++;
            }
            if (maxHeap.isEmpty()) break;
            w += maxHeap.poll();
        }
        return w;
    }
    
    public static void main(String[] args) {
        Problem14_IPO sol = new Problem14_IPO();
        System.out.println(sol.findMaximizedCapital(2, 0, new int[]{1,2,3}, new int[]{0,1,1})); // 4
        System.out.println(sol.findMaximizedCapital(3, 0, new int[]{1,2,3}, new int[]{0,1,2})); // 6
    }
}

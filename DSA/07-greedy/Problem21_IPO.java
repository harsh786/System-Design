/**
 * Problem 21: IPO (LeetCode 502)
 *
 * Greedy Choice: Among affordable projects, always pick the most profitable one.
 *
 * Time: O(n log n), Space: O(n)
 *
 * Production Analogy: Investment portfolio building - pick highest ROI projects affordable with current capital.
 */
import java.util.*;
public class Problem21_IPO {
    
    public static int findMaximizedCapital(int k, int w, int[] profits, int[] capital) {
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
        System.out.println(findMaximizedCapital(2, 0, new int[]{1,2,3}, new int[]{0,1,1})); // 4
        System.out.println(findMaximizedCapital(3, 0, new int[]{1,2,3}, new int[]{0,1,2})); // 6
    }
}

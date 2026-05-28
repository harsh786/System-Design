import java.util.*;

/**
 * Problem 21: Single-Threaded CPU (LeetCode 1834)
 * 
 * Approach: Sort tasks by enqueue time. Use min-heap by processing time then index.
 * Simulate CPU picking shortest available task.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Single-threaded event loop (Node.js) scheduling - shortest
 * job first among available tasks in the microtask queue.
 */
public class Problem21_SingleThreadedCPU {
    
    public int[] getOrder(int[][] tasks) {
        int n = tasks.length;
        int[][] indexed = new int[n][3];
        for (int i = 0; i < n; i++) indexed[i] = new int[]{tasks[i][0], tasks[i][1], i};
        Arrays.sort(indexed, (a, b) -> a[0] - b[0]);
        
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> 
            a[1] != b[1] ? a[1] - b[1] : a[2] - b[2]);
        
        int[] result = new int[n];
        int idx = 0, ri = 0;
        long time = indexed[0][0];
        
        while (ri < n) {
            while (idx < n && indexed[idx][0] <= time) pq.offer(indexed[idx++]);
            if (pq.isEmpty()) {
                time = indexed[idx][0];
                continue;
            }
            int[] task = pq.poll();
            result[ri++] = task[2];
            time += task[1];
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem21_SingleThreadedCPU sol = new Problem21_SingleThreadedCPU();
        System.out.println(Arrays.toString(sol.getOrder(new int[][]{{1,2},{2,4},{3,2},{4,1}})));
        // [0, 2, 3, 1]
        System.out.println(Arrays.toString(sol.getOrder(new int[][]{{7,10},{7,12},{7,5},{7,4},{7,2}})));
        // [4, 3, 2, 0, 1]
    }
}

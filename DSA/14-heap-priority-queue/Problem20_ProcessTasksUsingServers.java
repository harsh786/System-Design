import java.util.*;

/**
 * Problem 20: Process Tasks Using Servers (LeetCode 1882)
 * 
 * Approach: Two heaps - available servers (by weight, then index) and busy servers (by free time).
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Load balancer assigning incoming requests to the least loaded
 * server, with servers becoming available after processing completes.
 */
public class Problem20_ProcessTasksUsingServers {
    
    public int[] assignTasks(int[] servers, int[] tasks) {
        // [weight, index]
        PriorityQueue<int[]> available = new PriorityQueue<>((a, b) -> 
            a[0] != b[0] ? a[0] - b[0] : a[1] - b[1]);
        // [freeTime, weight, index]
        PriorityQueue<int[]> busy = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        
        for (int i = 0; i < servers.length; i++) available.offer(new int[]{servers[i], i});
        
        int[] result = new int[tasks.length];
        for (int t = 0; t < tasks.length; t++) {
            // Free up servers
            while (!busy.isEmpty() && busy.peek()[0] <= t) {
                int[] s = busy.poll();
                available.offer(new int[]{s[1], s[2]});
            }
            if (available.isEmpty()) {
                int[] s = busy.poll();
                // Free all servers at this time
                available.offer(new int[]{s[1], s[2]});
                while (!busy.isEmpty() && busy.peek()[0] == s[0]) {
                    int[] s2 = busy.poll();
                    available.offer(new int[]{s2[1], s2[2]});
                }
                int[] chosen = available.poll();
                result[t] = chosen[1];
                busy.offer(new int[]{s[0] + tasks[t], chosen[0], chosen[1]});
            } else {
                int[] chosen = available.poll();
                result[t] = chosen[1];
                busy.offer(new int[]{t + tasks[t], chosen[0], chosen[1]});
            }
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem20_ProcessTasksUsingServers sol = new Problem20_ProcessTasksUsingServers();
        System.out.println(Arrays.toString(sol.assignTasks(new int[]{3,3,2}, new int[]{1,2,3,2,1,2})));
        // [2,2,0,2,1,2]
    }
}

import java.util.*;

/**
 * Problem 5: Task Scheduler (LeetCode 621)
 * 
 * Approach: Max-heap for task frequencies + cooldown queue. Greedily schedule
 * the most frequent task available.
 * 
 * Time Complexity: O(N * n) where N = total tasks, n = cooldown
 * Space Complexity: O(26) = O(1)
 * 
 * Production Analogy: CPU task scheduling with cooldown periods, rate-limited
 * API call scheduling, or job queue management with backoff intervals.
 */
public class Problem05_TaskScheduler {
    
    public int leastInterval(char[] tasks, int n) {
        int[] freq = new int[26];
        for (char c : tasks) freq[c - 'A']++;
        
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        for (int f : freq) if (f > 0) maxHeap.offer(f);
        
        Queue<int[]> cooldown = new LinkedList<>(); // [count, available_time]
        int time = 0;
        
        while (!maxHeap.isEmpty() || !cooldown.isEmpty()) {
            time++;
            if (!maxHeap.isEmpty()) {
                int count = maxHeap.poll() - 1;
                if (count > 0) cooldown.offer(new int[]{count, time + n});
            }
            if (!cooldown.isEmpty() && cooldown.peek()[1] == time) {
                maxHeap.offer(cooldown.poll()[0]);
            }
        }
        return time;
    }
    
    public static void main(String[] args) {
        Problem05_TaskScheduler sol = new Problem05_TaskScheduler();
        System.out.println(sol.leastInterval(new char[]{'A','A','A','B','B','B'}, 2)); // 8
        System.out.println(sol.leastInterval(new char[]{'A','A','A','B','B','B'}, 0)); // 6
        System.out.println(sol.leastInterval(new char[]{'A','A','A','A','A','A','B','C','D','E','F','G'}, 2)); // 16
    }
}

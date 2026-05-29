/**
 * Problem: Task Scheduler Simulation (LeetCode 621 - simulation approach)
 * Approach: Simulate rounds using max-heap and cooldown queue
 * Complexity: O(n * interval) time, O(26) space
 * Production Analogy: CPU task scheduling with cooldown/rate limiting
 */
import java.util.*;
public class Problem42_TaskSchedulerSimulation {
    public int leastInterval(char[] tasks, int n) {
        int[] freq = new int[26];
        for (char t : tasks) freq[t-'A']++;
        PriorityQueue<Integer> pq = new PriorityQueue<>(Collections.reverseOrder());
        for (int f : freq) if (f > 0) pq.offer(f);
        int time = 0;
        Queue<int[]> cooldown = new LinkedList<>(); // [count, availableTime]
        while (!pq.isEmpty() || !cooldown.isEmpty()) {
            time++;
            if (!pq.isEmpty()) {
                int cnt = pq.poll() - 1;
                if (cnt > 0) cooldown.offer(new int[]{cnt, time+n});
            }
            if (!cooldown.isEmpty() && cooldown.peek()[1] == time)
                pq.offer(cooldown.poll()[0]);
        }
        return time;
    }
    public static void main(String[] args) {
        System.out.println(new Problem42_TaskSchedulerSimulation()
            .leastInterval(new char[]{'A','A','A','B','B','B'}, 2)); // 8
    }
}

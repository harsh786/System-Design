import java.util.*;

public class Problem18_TaskSchedulerQueueSimulation {
    public static int leastInterval(char[] tasks, int n) {
        int[] freq = new int[26];
        for (char c : tasks) freq[c - 'A']++;
        PriorityQueue<Integer> pq = new PriorityQueue<>(Collections.reverseOrder());
        for (int f : freq) if (f > 0) pq.offer(f);
        Queue<int[]> cooldown = new LinkedList<>();
        int time = 0;
        while (!pq.isEmpty() || !cooldown.isEmpty()) {
            time++;
            if (!pq.isEmpty()) {
                int cnt = pq.poll() - 1;
                if (cnt > 0) cooldown.offer(new int[]{cnt, time + n});
            }
            if (!cooldown.isEmpty() && cooldown.peek()[1] == time) pq.offer(cooldown.poll()[0]);
        }
        return time;
    }
    public static void main(String[] args) {
        System.out.println(leastInterval(new char[]{'A','A','A','B','B','B'}, 2)); // 8
    }
}

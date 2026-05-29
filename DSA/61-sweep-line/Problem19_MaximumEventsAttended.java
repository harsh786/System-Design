import java.util.*;

public class Problem19_MaximumEventsAttended {
    public int maxEvents(int[][] events) {
        Arrays.sort(events, (a, b) -> a[0] - b[0]);
        PriorityQueue<Integer> pq = new PriorityQueue<>();
        int i = 0, count = 0, day = 0;
        while (i < events.length || !pq.isEmpty()) {
            if (pq.isEmpty()) day = events[i][0];
            while (i < events.length && events[i][0] <= day) pq.offer(events[i++][1]);
            while (!pq.isEmpty() && pq.peek() < day) pq.poll();
            if (!pq.isEmpty()) { pq.poll(); count++; }
            day++;
        }
        return count;
    }

    public static void main(String[] args) {
        Problem19_MaximumEventsAttended sol = new Problem19_MaximumEventsAttended();
        System.out.println(sol.maxEvents(new int[][]{{1,2},{2,3},{3,4}})); // 3
    }
}

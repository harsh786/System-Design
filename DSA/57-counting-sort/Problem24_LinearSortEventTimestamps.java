import java.util.*;

public class Problem24_LinearSortEventTimestamps {
    // Sort events by hour bucket
    public static int[][] sortByHour(int[][] events) { // [timestamp, eventId]
        List<int[]>[] buckets = new List[24];
        for (int i = 0; i < 24; i++) buckets[i] = new ArrayList<>();
        for (int[] e : events) buckets[e[0] / 3600 % 24].add(e);
        int idx = 0;
        for (List<int[]> b : buckets) for (int[] e : b) events[idx++] = e;
        return events;
    }

    public static void main(String[] args) {
        int[][] events = {{7200,1},{3600,2},{0,3},{10800,4}};
        sortByHour(events);
        for (int[] e : events) System.out.println(Arrays.toString(e));
    }
}

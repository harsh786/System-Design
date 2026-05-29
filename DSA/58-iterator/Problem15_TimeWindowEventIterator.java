import java.util.*;

public class Problem15_TimeWindowEventIterator implements Iterator<int[]> {
    // Iterate events within a time window [start, end)
    int[][] events; // sorted by time: [timestamp, data]
    int idx;
    int windowStart, windowEnd;

    public Problem15_TimeWindowEventIterator(int[][] events, int start, int end) {
        this.events = events; windowStart = start; windowEnd = end;
        idx = 0;
        while (idx < events.length && events[idx][0] < windowStart) idx++;
    }

    public boolean hasNext() { return idx < events.length && events[idx][0] < windowEnd; }
    public int[] next() { return events[idx++]; }

    public static void main(String[] args) {
        int[][] events = {{1,10},{3,20},{5,30},{7,40},{9,50}};
        Problem15_TimeWindowEventIterator it = new Problem15_TimeWindowEventIterator(events, 3, 8);
        while (it.hasNext()) System.out.println(Arrays.toString(it.next()));
    }
}

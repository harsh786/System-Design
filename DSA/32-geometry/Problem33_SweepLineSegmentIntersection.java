import java.util.*;

public class Problem33_SweepLineSegmentIntersection {
    // Simplified: detect if any two horizontal/vertical segments intersect using sweep line
    static class Event implements Comparable<Event> {
        int x, type; int[] seg; // type: 0=start, 1=end, 2=vertical
        Event(int x, int type, int[] seg) { this.x = x; this.type = type; this.seg = seg; }
        public int compareTo(Event o) { return this.x != o.x ? this.x - o.x : this.type - o.type; }
    }
    public static int countIntersections(int[][] horizontals, int[][] verticals) {
        List<Event> events = new ArrayList<>();
        for (int[] h : horizontals) { // h = {x1, x2, y}
            events.add(new Event(h[0], 0, h)); events.add(new Event(h[1], 1, h));
        }
        for (int[] v : verticals) events.add(new Event(v[0], 2, v)); // v = {x, y1, y2}
        Collections.sort(events);
        TreeMap<Integer, Integer> active = new TreeMap<>(); // y values of active horizontal segments
        int count = 0;
        for (Event e : events) {
            if (e.type == 0) active.merge(e.seg[2], 1, Integer::sum);
            else if (e.type == 1) { active.merge(e.seg[2], -1, Integer::sum); if (active.get(e.seg[2]) == 0) active.remove(e.seg[2]); }
            else count += active.subMap(e.seg[1], true, e.seg[2], true).size();
        }
        return count;
    }
    public static void main(String[] args) {
        int[][] h = {{1,5,3},{1,5,7}}; // horizontal: x1,x2,y
        int[][] v = {{3,1,8}};          // vertical: x,y1,y2
        System.out.println(countIntersections(h, v)); // 2
    }
}

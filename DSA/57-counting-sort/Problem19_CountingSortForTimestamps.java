import java.util.*;

public class Problem19_CountingSortForTimestamps {
    // Sort events by second-of-day (0-86399)
    static class Event { int secondOfDay; String name;
        Event(int s, String n) { secondOfDay=s; name=n; }
        public String toString() { return name+"@"+secondOfDay; }
    }

    public static List<Event> sortByTime(List<Event> events) {
        int max = 86400;
        List<Event>[] buckets = new List[max];
        for (Event e : events) {
            if (buckets[e.secondOfDay] == null) buckets[e.secondOfDay] = new ArrayList<>();
            buckets[e.secondOfDay].add(e);
        }
        List<Event> sorted = new ArrayList<>();
        for (int i = 0; i < max; i++) if (buckets[i] != null) sorted.addAll(buckets[i]);
        return sorted;
    }

    public static void main(String[] args) {
        List<Event> events = Arrays.asList(new Event(3600,"login"), new Event(1800,"boot"), new Event(7200,"logout"));
        System.out.println(sortByTime(events));
    }
}

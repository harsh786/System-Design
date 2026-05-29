import java.util.*;

public class Problem47_SessionWindowAggregation {
    // Session Window: Group events with gaps < timeout into sessions.
    
    long sessionTimeout;
    Map<String, List<long[]>> sessions = new HashMap<>(); // key -> list of [start, end, count]
    
    public Problem47_SessionWindowAggregation() { this.sessionTimeout = 5000; }
    
    public void init(long timeout) { this.sessionTimeout = timeout; }
    
    public String addEvent(String key, long timestamp) {
        List<long[]> keySessions = sessions.computeIfAbsent(key, k -> new ArrayList<>());
        if (keySessions.isEmpty() || timestamp - keySessions.get(keySessions.size()-1)[1] > sessionTimeout) {
            keySessions.add(new long[]{timestamp, timestamp, 1});
            return "NEW_SESSION for " + key;
        } else {
            long[] last = keySessions.get(keySessions.size()-1);
            last[1] = timestamp;
            last[2]++;
            return "EXTEND_SESSION for " + key + " (count=" + last[2] + ")";
        }
    }
    
    public List<String> closedSessions(String key, long currentTime) {
        List<String> closed = new ArrayList<>();
        List<long[]> keySessions = sessions.getOrDefault(key, new ArrayList<>());
        Iterator<long[]> it = keySessions.iterator();
        while (it.hasNext()) {
            long[] s = it.next();
            if (currentTime - s[1] > sessionTimeout) {
                closed.add("Session[" + s[0] + "-" + s[1] + "] count=" + s[2]);
                it.remove();
            }
        }
        return closed;
    }
    
    public static void main(String[] args) {
        Problem47_SessionWindowAggregation sol = new Problem47_SessionWindowAggregation();
        sol.init(3000);
        System.out.println(sol.addEvent("user1", 1000));
        System.out.println(sol.addEvent("user1", 2000));
        System.out.println(sol.addEvent("user1", 4000));
        System.out.println(sol.addEvent("user1", 9000)); // new session (gap > 3000)
        System.out.println("Closed: " + sol.closedSessions("user1", 13000));
    }
}

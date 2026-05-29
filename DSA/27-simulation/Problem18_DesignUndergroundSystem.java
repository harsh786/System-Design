/**
 * Problem: Design Underground System (LeetCode 1396)
 * Approach: Two maps - active trips and completed route stats
 * Complexity: O(1) per operation
 * Production Analogy: Real-time metrics aggregation for service latency monitoring
 */
import java.util.*;
public class Problem18_DesignUndergroundSystem {
    Map<Integer, String[]> checkIns = new HashMap<>(); // id -> [station, time]
    Map<String, double[]> routes = new HashMap<>(); // route -> [totalTime, count]

    public void checkIn(int id, String station, int t) {
        checkIns.put(id, new String[]{station, String.valueOf(t)});
    }
    public void checkOut(int id, String station, int t) {
        String[] in = checkIns.remove(id);
        String route = in[0] + "->" + station;
        double[] stats = routes.getOrDefault(route, new double[2]);
        stats[0] += t - Integer.parseInt(in[1]);
        stats[1]++;
        routes.put(route, stats);
    }
    public double getAverageTime(String start, String end) {
        double[] stats = routes.get(start + "->" + end);
        return stats[0] / stats[1];
    }
    public static void main(String[] args) {
        Problem18_DesignUndergroundSystem sys = new Problem18_DesignUndergroundSystem();
        sys.checkIn(1, "A", 3); sys.checkOut(1, "B", 8);
        sys.checkIn(2, "A", 5); sys.checkOut(2, "B", 12);
        System.out.println(sys.getAverageTime("A", "B")); // 6.0
    }
}

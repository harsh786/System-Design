import java.util.*;

/**
 * Problem 40: Design Underground System
 * Track check-ins/check-outs and calculate average travel time between stations.
 *
 * Approach: Two HashMaps - one for active trips (id -> (station, time)),
 * one for route stats (route -> (totalTime, count)).
 *
 * Time Complexity: O(1) all operations
 * Space Complexity: O(n + r) where r = number of routes
 *
 * Production Analogy: This IS a transit analytics system. Same pattern used
 * in Uber/Lyft for average ETA computation between zones.
 */
public class Problem40_DesignUndergroundSystem {
    private Map<Integer, String[]> checkIns = new HashMap<>(); // id -> [station, time]
    private Map<String, long[]> routeStats = new HashMap<>();  // route -> [totalTime, count]

    public void checkIn(int id, String stationName, int t) {
        checkIns.put(id, new String[]{stationName, String.valueOf(t)});
    }

    public void checkOut(int id, String stationName, int t) {
        String[] in = checkIns.remove(id);
        String route = in[0] + "->" + stationName;
        long[] stats = routeStats.computeIfAbsent(route, k -> new long[2]);
        stats[0] += t - Integer.parseInt(in[1]);
        stats[1]++;
    }

    public double getAverageTime(String startStation, String endStation) {
        long[] stats = routeStats.get(startStation + "->" + endStation);
        return (double) stats[0] / stats[1];
    }

    public static void main(String[] args) {
        Problem40_DesignUndergroundSystem sys = new Problem40_DesignUndergroundSystem();
        sys.checkIn(45, "Leyton", 3);
        sys.checkIn(32, "Paradise", 8);
        sys.checkIn(27, "Leyton", 10);
        sys.checkOut(45, "Waterloo", 15);
        sys.checkOut(27, "Waterloo", 20);
        sys.checkOut(32, "Cambridge", 22);
        System.out.println(sys.getAverageTime("Paradise", "Cambridge")); // 14.0
        System.out.println(sys.getAverageTime("Leyton", "Waterloo")); // 11.0
    }
}

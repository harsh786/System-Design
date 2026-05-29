import java.util.*;

/**
 * Problem 14: Design Underground System
 * 
 * API Contract:
 * - checkIn(id, stationName, t): Customer checks in
 * - checkOut(id, stationName, t): Customer checks out
 * - getAverageTime(start, end): Average travel time between stations
 * 
 * Complexity: O(1) for all operations
 * Data Structure: Two HashMaps - active trips + route statistics
 * 
 * Production Analogy: Metro/subway analytics, ride-sharing ETAs,
 * network latency monitoring between data centers
 */
public class Problem14_DesignUndergroundSystem {

    static class UndergroundSystem {
        private Map<Integer, String[]> checkIns; // id -> [station, time]
        private Map<String, double[]> routes; // "start->end" -> [totalTime, count]

        public UndergroundSystem() {
            checkIns = new HashMap<>();
            routes = new HashMap<>();
        }

        public void checkIn(int id, String stationName, int t) {
            checkIns.put(id, new String[]{stationName, String.valueOf(t)});
        }

        public void checkOut(int id, String stationName, int t) {
            String[] info = checkIns.remove(id);
            String route = info[0] + "->" + stationName;
            double time = t - Integer.parseInt(info[1]);
            double[] stats = routes.getOrDefault(route, new double[]{0, 0});
            stats[0] += time;
            stats[1]++;
            routes.put(route, stats);
        }

        public double getAverageTime(String startStation, String endStation) {
            double[] stats = routes.get(startStation + "->" + endStation);
            return stats[0] / stats[1];
        }
    }

    public static void main(String[] args) {
        UndergroundSystem us = new UndergroundSystem();
        us.checkIn(1, "A", 3);
        us.checkOut(1, "B", 8);
        assert us.getAverageTime("A", "B") == 5.0;

        us.checkIn(2, "A", 10);
        us.checkOut(2, "B", 16);
        assert us.getAverageTime("A", "B") == 5.5; // (5+6)/2

        us.checkIn(3, "A", 20);
        us.checkOut(3, "B", 30);
        assert Math.abs(us.getAverageTime("A", "B") - 7.0) < 0.001; // (5+6+10)/3

        System.out.println("All tests passed!");
    }
}

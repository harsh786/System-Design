import java.util.*;

public class Problem23_DesignUndergroundSystem {
    // 1396. Design Underground System.
    
    Map<Integer, String[]> checkIns = new HashMap<>(); // id -> [station, time]
    Map<String, long[]> trips = new HashMap<>(); // "A->B" -> [totalTime, count]
    
    public void checkIn(int id, String stationName, int t) {
        checkIns.put(id, new String[]{stationName, String.valueOf(t)});
    }
    
    public void checkOut(int id, String stationName, int t) {
        String[] in = checkIns.remove(id);
        String key = in[0] + "->" + stationName;
        long[] data = trips.computeIfAbsent(key, k -> new long[2]);
        data[0] += t - Integer.parseInt(in[1]);
        data[1]++;
    }
    
    public double getAverageTime(String startStation, String endStation) {
        long[] data = trips.get(startStation + "->" + endStation);
        return (double) data[0] / data[1];
    }
    
    public static void main(String[] args) {
        Problem23_DesignUndergroundSystem sol = new Problem23_DesignUndergroundSystem();
        sol.checkIn(1, "A", 3); sol.checkOut(1, "B", 8);
        sol.checkIn(2, "A", 5); sol.checkOut(2, "B", 12);
        System.out.println(sol.getAverageTime("A", "B")); // 6.0
    }
}

import java.util.*;

public class Problem16_BusRoutes {
    public static int numBusesToDestination(int[][] routes, int source, int target) {
        if (source == target) return 0;
        Map<Integer, List<Integer>> stopToBus = new HashMap<>();
        for (int i = 0; i < routes.length; i++)
            for (int s : routes[i]) stopToBus.computeIfAbsent(s, k -> new ArrayList<>()).add(i);
        Queue<Integer> q = new LinkedList<>();
        Set<Integer> visitedStops = new HashSet<>(), visitedBuses = new HashSet<>();
        q.offer(source); visitedStops.add(source);
        int level = 0;
        while (!q.isEmpty()) {
            level++;
            for (int sz = q.size(); sz > 0; sz--) {
                int stop = q.poll();
                for (int bus : stopToBus.getOrDefault(stop, new ArrayList<>())) {
                    if (visitedBuses.contains(bus)) continue;
                    visitedBuses.add(bus);
                    for (int s : routes[bus]) {
                        if (s == target) return level;
                        if (visitedStops.add(s)) q.offer(s);
                    }
                }
            }
        }
        return -1;
    }
    public static void main(String[] args) {
        System.out.println(numBusesToDestination(new int[][]{{1,2,7},{3,6,7}}, 1, 6)); // 2
    }
}

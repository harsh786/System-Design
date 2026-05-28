import java.util.*;

/**
 * Problem: Bus Routes (LeetCode 815)
 * Approach: BFS on routes (not stops) - build stop-to-routes mapping
 * Time: O(N*M) N=routes, M=stops per route, Space: O(N*M)
 * Production Analogy: Minimum service hops to reach a destination through shared infrastructure
 */
public class Problem11_BusRoutes {
    public int numBusesToDestination(int[][] routes, int source, int target) {
        if (source == target) return 0;
        Map<Integer, List<Integer>> stopToRoutes = new HashMap<>();
        for (int i = 0; i < routes.length; i++)
            for (int stop : routes[i])
                stopToRoutes.computeIfAbsent(stop, k -> new ArrayList<>()).add(i);
        Queue<Integer> q = new LinkedList<>();
        Set<Integer> visitedStops = new HashSet<>(), visitedRoutes = new HashSet<>();
        q.offer(source); visitedStops.add(source);
        int buses = 0;
        while (!q.isEmpty()) {
            int size = q.size(); buses++;
            for (int i = 0; i < size; i++) {
                int stop = q.poll();
                for (int route : stopToRoutes.getOrDefault(stop, Collections.emptyList())) {
                    if (visitedRoutes.contains(route)) continue;
                    visitedRoutes.add(route);
                    for (int next : routes[route]) {
                        if (next == target) return buses;
                        if (visitedStops.add(next)) q.offer(next);
                    }
                }
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        int[][] routes = {{1,2,7},{3,6,7}};
        System.out.println(new Problem11_BusRoutes().numBusesToDestination(routes, 1, 6)); // 2
    }
}

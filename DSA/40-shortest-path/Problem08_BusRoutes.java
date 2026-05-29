import java.util.*;

/**
 * Problem: Bus Routes
 * Minimum buses to take from source stop to target stop.
 *
 * Approach: BFS on route graph (nodes = bus routes, edges = shared stops)
 *
 * Time Complexity: O(N^2 * S) where N=routes, S=stops per route
 * Space Complexity: O(N * S)
 *
 * Production Analogy: Minimum service hops in a multi-cluster routing setup.
 */
public class Problem08_BusRoutes {

    public int numBusesToDestination(int[][] routes, int source, int target) {
        if (source == target) return 0;
        Map<Integer, List<Integer>> stopToRoutes = new HashMap<>();
        for (int i = 0; i < routes.length; i++)
            for (int stop : routes[i])
                stopToRoutes.computeIfAbsent(stop, k -> new ArrayList<>()).add(i);

        Queue<Integer> q = new LinkedList<>();
        Set<Integer> visitedRoutes = new HashSet<>(), visitedStops = new HashSet<>();
        visitedStops.add(source);

        for (int route : stopToRoutes.getOrDefault(source, Collections.emptyList())) {
            q.offer(route); visitedRoutes.add(route);
        }

        int buses = 1;
        while (!q.isEmpty()) {
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int route = q.poll();
                for (int stop : routes[route]) {
                    if (stop == target) return buses;
                    if (visitedStops.add(stop))
                        for (int nextRoute : stopToRoutes.get(stop))
                            if (visitedRoutes.add(nextRoute)) q.offer(nextRoute);
                }
            }
            buses++;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem08_BusRoutes solver = new Problem08_BusRoutes();
        System.out.println(solver.numBusesToDestination(new int[][]{{1,2,7},{3,6,7}}, 1, 6)); // 2
    }
}

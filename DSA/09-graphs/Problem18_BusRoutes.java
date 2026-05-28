import java.util.*;

/**
 * Problem 18: Bus Routes (LeetCode 815)
 * 
 * Approach: BFS on routes (not stops). Build stop-to-routes mapping. Each BFS level = 1 bus.
 * Time: O(N*M) where N=routes, M=stops per route, Space: O(N*M)
 * 
 * Production Analogy: Minimum service hops to route a request between two endpoints via shared buses (service meshes).
 */
public class Problem18_BusRoutes {
    
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
            buses++;
            int size = q.size();
            for (int i = 0; i < size; i++) {
                int stop = q.poll();
                for (int route : stopToRoutes.getOrDefault(stop, Collections.emptyList())) {
                    if (!visitedRoutes.add(route)) continue;
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
        Problem18_BusRoutes sol = new Problem18_BusRoutes();
        System.out.println(sol.numBusesToDestination(new int[][]{{1,2,7},{3,6,7}}, 1, 6)); // 2
        System.out.println(sol.numBusesToDestination(new int[][]{{7,12},{4,5,15},{6},{15,19},{9,12,13}}, 15, 12)); // -1
        System.out.println(sol.numBusesToDestination(new int[][]{{1,2,3}}, 1, 1)); // 0
    }
}

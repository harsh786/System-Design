import java.util.*;

public class Problem29_InteractiveNetworkDiscovery {
    // Discover network topology by querying connectivity
    static Set<Integer>[] network;
    static { network = new HashSet[5]; for(int i=0;i<5;i++) network[i]=new HashSet<>();
        network[0].add(1);network[1].add(0);network[1].add(2);network[2].add(1);
        network[2].add(3);network[3].add(2);network[3].add(4);network[4].add(3); }
    
    static boolean isConnected(int u, int v) { return network[u].contains(v); }
    
    static Map<Integer, Set<Integer>> discover(int n) {
        Map<Integer, Set<Integer>> discovered = new HashMap<>();
        Queue<Integer> q = new LinkedList<>(); q.add(0);
        Set<Integer> visited = new HashSet<>(); visited.add(0);
        while (!q.isEmpty()) {
            int u = q.poll();
            discovered.putIfAbsent(u, new HashSet<>());
            for (int v = 0; v < n; v++) {
                if (v != u && isConnected(u, v)) {
                    discovered.get(u).add(v);
                    if (!visited.contains(v)) { visited.add(v); q.add(v); }
                }
            }
        }
        return discovered;
    }
    
    public static void main(String[] args) {
        Map<Integer, Set<Integer>> topo = discover(5);
        topo.forEach((k, v) -> System.out.println(k + " -> " + v));
    }
}

import java.util.*;

/**
 * Problem 32: Find All People With Secret (LeetCode 2092)
 * 
 * Person 0 shares secret with firstPerson at time 0. Meetings [x,y,time] happen.
 * At each time, if someone in a meeting knows the secret, the other learns it.
 * Find all who know the secret.
 * 
 * Approach: Process meetings by time. At each timestamp, union meeting participants.
 * After processing a timestamp, disconnect those not connected to person 0.
 * 
 * Time: O(M*logM + M*α(n)), Space: O(n + M)
 * 
 * Production Analogy: Secret/credential propagation in a timed communication graph -
 * tracking which services receive a rotated key at each sync interval.
 */
public class Problem32_FindAllPeopleWithSecret {
    
    int[] parent, rank;
    
    public List<Integer> findAllPeople(int n, int[][] meetings, int firstPerson) {
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        union(0, firstPerson);
        
        // Group meetings by time
        TreeMap<Integer, List<int[]>> byTime = new TreeMap<>();
        for (int[] m : meetings) byTime.computeIfAbsent(m[2], k -> new ArrayList<>()).add(m);
        
        for (var entry : byTime.entrySet()) {
            List<int[]> mts = entry.getValue();
            Set<Integer> involved = new HashSet<>();
            
            for (int[] m : mts) {
                union(m[0], m[1]);
                involved.add(m[0]);
                involved.add(m[1]);
            }
            
            // Reset those not connected to 0
            for (int p : involved) {
                if (find(p) != find(0)) {
                    parent[p] = p;
                    rank[p] = 0;
                }
            }
        }
        
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < n; i++) if (find(i) == find(0)) result.add(i);
        return result;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        if (rank[px] < rank[py]) parent[px] = py;
        else if (rank[px] > rank[py]) parent[py] = px;
        else { parent[py] = px; rank[px]++; }
    }
    
    public static void main(String[] args) {
        Problem32_FindAllPeopleWithSecret sol = new Problem32_FindAllPeopleWithSecret();
        System.out.println(sol.findAllPeople(6, new int[][]{{1,2,5},{2,3,8},{1,5,10}}, 1));
        // [0, 1, 2, 3, 5]
        
        sol = new Problem32_FindAllPeopleWithSecret();
        System.out.println(sol.findAllPeople(4, new int[][]{{3,1,3},{1,2,2},{0,3,3}}, 3));
        // [0, 1, 3]
    }
}

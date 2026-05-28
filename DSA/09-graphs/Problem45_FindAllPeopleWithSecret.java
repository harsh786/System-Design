import java.util.*;

/**
 * Problem 45: Find All People With Secret (LeetCode 2092)
 * 
 * Approach: Process meetings sorted by time. At each time step, union people who meet.
 * After processing a time step, disconnect those not connected to person 0.
 * Time: O(M log M + M * α(N)), Space: O(N + M)
 * 
 * Production Analogy: Tracking secret/config propagation through time-ordered inter-service communications.
 */
public class Problem45_FindAllPeopleWithSecret {
    
    int[] parent, rank;
    int find(int x) { return parent[x] == x ? x : (parent[x] = find(parent[x])); }
    void union(int a, int b) { int pa=find(a),pb=find(b); if(pa!=pb){if(rank[pa]<rank[pb])parent[pa]=pb;else if(rank[pa]>rank[pb])parent[pb]=pa;else{parent[pb]=pa;rank[pa]++;}}}
    
    public List<Integer> findAllPeople(int n, int[][] meetings, int firstPerson) {
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        union(0, firstPerson);
        
        Arrays.sort(meetings, (a,b) -> a[2] - b[2]);
        int i = 0;
        while (i < meetings.length) {
            int time = meetings[i][2];
            List<int[]> group = new ArrayList<>();
            while (i < meetings.length && meetings[i][2] == time) { group.add(meetings[i]); i++; }
            for (int[] m : group) union(m[0], m[1]);
            // Reset those not connected to 0
            for (int[] m : group) {
                if (find(m[0]) != find(0)) { parent[m[0]] = m[0]; rank[m[0]] = 0; }
                if (find(m[1]) != find(0)) { parent[m[1]] = m[1]; rank[m[1]] = 0; }
            }
        }
        List<Integer> result = new ArrayList<>();
        for (int j = 0; j < n; j++) if (find(j) == find(0)) result.add(j);
        return result;
    }
    
    public static void main(String[] args) {
        Problem45_FindAllPeopleWithSecret sol = new Problem45_FindAllPeopleWithSecret();
        System.out.println(sol.findAllPeople(6, new int[][]{{1,2,5},{2,3,8},{1,5,10}}, 1)); // [0,1,2,3,5]
        sol = new Problem45_FindAllPeopleWithSecret();
        System.out.println(sol.findAllPeople(4, new int[][]{{3,1,3},{1,2,2},{0,3,3}}, 3)); // [0,1,3]
    }
}

import java.util.*;

/**
 * Problem 48: The Earliest Moment When Everyone Become Friends (variant)
 * 
 * Extended version: Also return the sequence of component counts over time,
 * and handle duplicate timestamps.
 * 
 * Time: O(E*logE + E*α(n)), Space: O(n + E)
 * 
 * Production Analogy: Monitoring cluster formation over time - dashboard showing
 * how quickly nodes discover each other in a mesh network.
 */
public class Problem48_TheEarliestMomentWhenEveryoneBecomeFriends {
    
    int[] parent, rank;
    int components;
    
    public int[] solve(int n, int[][] logs) {
        Arrays.sort(logs, (a, b) -> a[0] - b[0]);
        parent = new int[n]; rank = new int[n]; components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
        
        int earliestTime = -1;
        List<int[]> timeline = new ArrayList<>(); // [time, components]
        
        for (int[] log : logs) {
            union(log[1], log[2]);
            timeline.add(new int[]{log[0], components});
            if (components == 1 && earliestTime == -1) earliestTime = log[0];
        }
        
        System.out.println("Timeline:");
        for (int[] t : timeline) System.out.println("  Time " + t[0] + ": " + t[1] + " components");
        
        return new int[]{earliestTime, components};
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
        components--;
    }
    
    public static void main(String[] args) {
        Problem48_TheEarliestMomentWhenEveryoneBecomeFriends sol = new Problem48_TheEarliestMomentWhenEveryoneBecomeFriends();
        int[] res = sol.solve(4, new int[][]{{1,0,1},{2,1,2},{3,2,3},{4,0,3}});
        System.out.println("Earliest: " + res[0] + ", Final components: " + res[1]); // 3, 1
        
        sol = new Problem48_TheEarliestMomentWhenEveryoneBecomeFriends();
        res = sol.solve(4, new int[][]{{1,0,1},{2,2,3}});
        System.out.println("Earliest: " + res[0] + ", Final components: " + res[1]); // -1, 2
    }
}

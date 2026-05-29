import java.util.*;

/**
 * Problem 47: Earliest Moment When Everyone Become Friends (LeetCode 1101)
 * 
 * Given timestamped friendships, find earliest time when all are in one group.
 * 
 * Approach: Sort by time, union friends. When components == 1, return that time.
 * 
 * Time: O(E*logE + E*α(n)), Space: O(n)
 * 
 * Production Analogy: Cluster convergence time - earliest moment all nodes in a
 * gossip protocol have converged to a single consistent view.
 */
public class Problem47_EarliestMomentWhenEveryoneBecomeFriends {
    
    int[] parent, rank;
    int components;
    
    public int earliestAcq(int[][] logs, int n) {
        Arrays.sort(logs, (a, b) -> a[0] - b[0]);
        parent = new int[n]; rank = new int[n]; components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
        
        for (int[] log : logs) {
            union(log[1], log[2]);
            if (components == 1) return log[0];
        }
        return -1;
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
        Problem47_EarliestMomentWhenEveryoneBecomeFriends sol = new Problem47_EarliestMomentWhenEveryoneBecomeFriends();
        System.out.println(sol.earliestAcq(new int[][]{
            {20190101,0,1},{20190104,3,4},{20190107,2,3},{20190211,1,5},
            {20190224,2,4},{20190301,0,3},{20190312,1,2},{20190322,4,5}}, 6)); // 20190301
    }
}

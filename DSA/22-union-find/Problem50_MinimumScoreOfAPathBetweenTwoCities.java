import java.util.*;

/**
 * Problem 50: Minimum Score of a Path Between Two Cities (LeetCode 2492)
 * 
 * Score of a path = minimum edge weight on that path. Find minimum possible
 * score of a path from city 1 to city n (can revisit nodes/edges).
 * 
 * Key insight: Since we can revisit, the answer is the minimum edge weight
 * in the entire connected component containing nodes 1 and n.
 * 
 * Approach: Union-Find to find component of node 1. Track minimum edge in that component.
 * 
 * Time: O(E * α(n)), Space: O(n)
 * 
 * Production Analogy: Finding the weakest link (minimum bandwidth) in any possible
 * route between two services in the same network partition.
 */
public class Problem50_MinimumScoreOfAPathBetweenTwoCities {
    
    int[] parent, rank;
    
    public int minScore(int n, int[][] roads) {
        parent = new int[n + 1]; rank = new int[n + 1];
        for (int i = 0; i <= n; i++) parent[i] = i;
        
        for (int[] r : roads) union(r[0], r[1]);
        
        int root1 = find(1);
        int minScore = Integer.MAX_VALUE;
        for (int[] r : roads) {
            if (find(r[0]) == root1) {
                minScore = Math.min(minScore, r[2]);
            }
        }
        return minScore;
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
        Problem50_MinimumScoreOfAPathBetweenTwoCities sol = new Problem50_MinimumScoreOfAPathBetweenTwoCities();
        System.out.println(sol.minScore(4, new int[][]{{1,2,9},{2,3,6},{2,4,5},{1,4,7}})); // 5
        
        sol = new Problem50_MinimumScoreOfAPathBetweenTwoCities();
        System.out.println(sol.minScore(4, new int[][]{{1,2,2},{1,3,4},{3,4,7}})); // 2
    }
}

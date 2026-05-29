import java.util.*;

/**
 * Problem 11: Couples Holding Hands (LeetCode 765)
 * 
 * N couples sit in 2N seats. Find minimum swaps so every couple sits together.
 * 
 * Approach: Each couple is a group. For seat pair (0,1), (2,3), etc., union the
 * couples sitting there. If k couples form a connected component, it takes k-1 swaps.
 * Answer = N - number of components.
 * 
 * Time: O(n * α(n)), Space: O(n)
 * 
 * Production Analogy: Data locality optimization - placing related data shards
 * on the same node. Each "swap" is a data migration operation to co-locate related data.
 */
public class Problem11_CouplesHoldingHands {
    
    int[] parent, rank;
    int components;
    
    public int minSwapsCouples(int[] row) {
        int n = row.length / 2;
        parent = new int[n]; rank = new int[n];
        components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
        
        for (int i = 0; i < row.length; i += 2) {
            int couple1 = row[i] / 2;
            int couple2 = row[i + 1] / 2;
            union(couple1, couple2);
        }
        return n - components;
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
        Problem11_CouplesHoldingHands sol = new Problem11_CouplesHoldingHands();
        System.out.println(sol.minSwapsCouples(new int[]{0,2,1,3})); // 1
        
        sol = new Problem11_CouplesHoldingHands();
        System.out.println(sol.minSwapsCouples(new int[]{3,2,0,1})); // 0
        
        sol = new Problem11_CouplesHoldingHands();
        System.out.println(sol.minSwapsCouples(new int[]{5,4,2,6,3,1,0,7})); // 2
    }
}

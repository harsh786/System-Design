import java.util.*;

/**
 * Problem 29: Most Stones Removed with Same Row or Column (LeetCode 947)
 * 
 * Approach: Union-Find. Stones in same row/col are connected. Answer = total - components.
 * Time: O(N * α(N)), Space: O(N)
 * 
 * Production Analogy: Decommissioning redundant servers that share network segments.
 */
public class Problem29_MostStonesRemoved {
    
    Map<Integer, Integer> parent = new HashMap<>();
    int components = 0;
    
    public int removeStones(int[][] stones) {
        for (int[] s : stones) { union(s[0], ~s[1]); }
        return stones.length - components;
    }
    
    int find(int x) { if (!parent.containsKey(x)) { parent.put(x, x); components++; }
        if (parent.get(x) != x) parent.put(x, find(parent.get(x)));
        return parent.get(x); }
    
    void union(int a, int b) { int pa = find(a), pb = find(b); if (pa != pb) { parent.put(pa, pb); components--; } }
    
    public static void main(String[] args) {
        Problem29_MostStonesRemoved sol = new Problem29_MostStonesRemoved();
        System.out.println(sol.removeStones(new int[][]{{0,0},{0,1},{1,0},{1,2},{2,1},{2,2}})); // 5
        sol = new Problem29_MostStonesRemoved(); sol.parent.clear(); sol.components=0;
        System.out.println(sol.removeStones(new int[][]{{0,0},{0,2},{1,1},{2,0},{2,2}})); // 3
    }
}

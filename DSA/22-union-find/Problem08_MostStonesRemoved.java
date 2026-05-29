import java.util.*;

/**
 * Problem 8: Most Stones Removed with Same Row or Column (LeetCode 947)
 * 
 * Stones on a 2D plane. Remove a stone if it shares a row or column with another.
 * Find maximum stones removable. Answer = total - number of connected components.
 * 
 * Approach: Union stones sharing row/column. Each component of size k can remove k-1 stones.
 * We union row index with ~col index to avoid collision.
 * 
 * Time: O(n * α(n)), Space: O(n)
 * 
 * Production Analogy: Database table deduplication - records that share a key
 * (row/column) can be merged, keeping only one canonical record per group.
 */
public class Problem08_MostStonesRemoved {
    
    Map<Integer, Integer> parent = new HashMap<>();
    int components = 0;
    
    public int removeStones(int[][] stones) {
        for (int[] s : stones) {
            union(s[0], ~s[1]); // Use complement for column to avoid collision with row
        }
        return stones.length - components;
    }
    
    private int find(int x) {
        if (!parent.containsKey(x)) {
            parent.put(x, x);
            components++;
        }
        if (parent.get(x) != x) {
            parent.put(x, find(parent.get(x)));
        }
        return parent.get(x);
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px != py) {
            parent.put(px, py);
            components--;
        }
    }
    
    public static void main(String[] args) {
        Problem08_MostStonesRemoved sol = new Problem08_MostStonesRemoved();
        System.out.println(sol.removeStones(new int[][]{{0,0},{0,1},{1,0},{1,2},{2,1},{2,2}})); // 5
        
        sol = new Problem08_MostStonesRemoved();
        System.out.println(sol.removeStones(new int[][]{{0,0},{0,2},{1,1},{2,0},{2,2}})); // 3
        
        sol = new Problem08_MostStonesRemoved();
        System.out.println(sol.removeStones(new int[][]{{0,0}})); // 0
    }
}

import java.util.*;

/**
 * Problem 27: Minimum Hamming Distance After Swap Operations (LeetCode 1722)
 * 
 * Given source, target arrays and allowed swaps on source, find minimum Hamming distance.
 * 
 * Approach: Union indices that can be swapped. Within each component, count how many
 * elements can be matched. Hamming distance = unmatched elements.
 * 
 * Time: O(n * α(n)), Space: O(n)
 * 
 * Production Analogy: Load rebalancing - given allowed migrations between servers,
 * minimize the number of misplaced items.
 */
public class Problem27_MinimumHammingDistanceAfterSwapOperations {
    
    int[] parent, rank;
    
    public int minimumHammingDistance(int[] source, int[] target, int[][] allowedSwaps) {
        int n = source.length;
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        for (int[] s : allowedSwaps) union(s[0], s[1]);
        
        // Group indices by component, count frequencies
        Map<Integer, Map<Integer, Integer>> groups = new HashMap<>();
        for (int i = 0; i < n; i++) {
            int root = find(i);
            groups.computeIfAbsent(root, k -> new HashMap<>())
                  .merge(source[i], 1, Integer::sum);
        }
        
        int dist = 0;
        for (int i = 0; i < n; i++) {
            int root = find(i);
            Map<Integer, Integer> freq = groups.get(root);
            if (freq.getOrDefault(target[i], 0) > 0) {
                freq.merge(target[i], -1, Integer::sum);
            } else {
                dist++;
            }
        }
        return dist;
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
        Problem27_MinimumHammingDistanceAfterSwapOperations sol = new Problem27_MinimumHammingDistanceAfterSwapOperations();
        System.out.println(sol.minimumHammingDistance(
            new int[]{1,2,3,4}, new int[]{2,1,4,5}, new int[][]{{0,1},{2,3}})); // 1
        System.out.println(sol.minimumHammingDistance(
            new int[]{1,2,3,4}, new int[]{1,3,2,4}, new int[][]{})); // 2
    }
}

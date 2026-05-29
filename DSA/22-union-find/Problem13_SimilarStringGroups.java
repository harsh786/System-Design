import java.util.*;

/**
 * Problem 13: Similar String Groups (LeetCode 839)
 * 
 * Two strings are similar if you can swap two letters to get one from the other.
 * Group similar strings transitively. Return number of groups.
 * 
 * Time: O(n² * m * α(n)) where m = string length, Space: O(n)
 * 
 * Production Analogy: Clustering similar configurations - configs that differ
 * by one swap are "similar" and should be grouped for deduplication.
 */
public class Problem13_SimilarStringGroups {
    
    int[] parent, rank;
    int components;
    
    public int numSimilarGroups(String[] strs) {
        int n = strs.length;
        parent = new int[n]; rank = new int[n];
        components = n;
        for (int i = 0; i < n; i++) parent[i] = i;
        
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++)
                if (isSimilar(strs[i], strs[j])) union(i, j);
        
        return components;
    }
    
    private boolean isSimilar(String a, String b) {
        int diff = 0;
        for (int i = 0; i < a.length(); i++) {
            if (a.charAt(i) != b.charAt(i)) diff++;
            if (diff > 2) return false;
        }
        return true;
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
        Problem13_SimilarStringGroups sol = new Problem13_SimilarStringGroups();
        System.out.println(sol.numSimilarGroups(new String[]{"tars","rats","arts","star"})); // 2
        
        sol = new Problem13_SimilarStringGroups();
        System.out.println(sol.numSimilarGroups(new String[]{"omv","ovm"})); // 1
    }
}

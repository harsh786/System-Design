import java.util.*;

/**
 * Problem 31: Smallest String With Swaps (LeetCode 1202)
 * 
 * Given string and allowed swap pairs, return lexicographically smallest string.
 * 
 * Approach: Union indices that can be swapped. Within each component,
 * sort characters and assign them to sorted positions.
 * 
 * Time: O(n*logn * α(n)), Space: O(n)
 * 
 * Production Analogy: Optimal resource assignment - given transferable resources
 * between nodes, find the globally optimal placement.
 */
public class Problem31_SmallestStringWithSwaps {
    
    int[] parent, rank;
    
    public String smallestStringWithSwaps(String s, List<List<Integer>> pairs) {
        int n = s.length();
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        for (List<Integer> p : pairs) union(p.get(0), p.get(1));
        
        Map<Integer, List<Integer>> groups = new HashMap<>();
        for (int i = 0; i < n; i++) groups.computeIfAbsent(find(i), k -> new ArrayList<>()).add(i);
        
        char[] result = new char[n];
        for (List<Integer> indices : groups.values()) {
            List<Character> chars = new ArrayList<>();
            for (int idx : indices) chars.add(s.charAt(idx));
            Collections.sort(chars);
            Collections.sort(indices);
            for (int i = 0; i < indices.size(); i++) result[indices.get(i)] = chars.get(i);
        }
        return new String(result);
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
        Problem31_SmallestStringWithSwaps sol = new Problem31_SmallestStringWithSwaps();
        System.out.println(sol.smallestStringWithSwaps("dcab",
            Arrays.asList(Arrays.asList(0,3), Arrays.asList(1,2)))); // "bacd"
        System.out.println(sol.smallestStringWithSwaps("dcab",
            Arrays.asList(Arrays.asList(0,3), Arrays.asList(1,2), Arrays.asList(0,2)))); // "abcd"
    }
}

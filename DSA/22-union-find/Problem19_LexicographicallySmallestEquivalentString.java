import java.util.*;

/**
 * Problem 19: Lexicographically Smallest Equivalent String (LeetCode 1061)
 * 
 * Given equivalence pairs from s1[i] and s2[i], transform baseStr using
 * the smallest equivalent character for each position.
 * 
 * Approach: Union characters that are equivalent. When unioning, always make
 * the smaller character the root (instead of union by rank, use union by value).
 * 
 * Time: O(n * α(26)) = O(n), Space: O(1)
 * 
 * Production Analogy: DNS CNAME resolution - multiple aliases point to a canonical
 * name, and we always want the "primary" (smallest) canonical form.
 */
public class Problem19_LexicographicallySmallestEquivalentString {
    
    int[] parent = new int[26];
    
    public String smallestEquivalentString(String s1, String s2, String baseStr) {
        for (int i = 0; i < 26; i++) parent[i] = i;
        
        for (int i = 0; i < s1.length(); i++) {
            union(s1.charAt(i) - 'a', s2.charAt(i) - 'a');
        }
        
        StringBuilder sb = new StringBuilder();
        for (char c : baseStr.toCharArray()) {
            sb.append((char)('a' + find(c - 'a')));
        }
        return sb.toString();
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        // Always make smaller char the root
        if (px < py) parent[py] = px;
        else parent[px] = py;
    }
    
    public static void main(String[] args) {
        Problem19_LexicographicallySmallestEquivalentString sol;
        
        sol = new Problem19_LexicographicallySmallestEquivalentString();
        System.out.println(sol.smallestEquivalentString("parker","morris","parser")); // "makkek"
        
        sol = new Problem19_LexicographicallySmallestEquivalentString();
        System.out.println(sol.smallestEquivalentString("hello","world","hold")); // "hdld"
    }
}

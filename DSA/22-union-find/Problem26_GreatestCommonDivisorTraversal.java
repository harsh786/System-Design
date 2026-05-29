import java.util.*;

/**
 * Problem 26: Greatest Common Divisor Traversal (LeetCode 2709)
 * 
 * Can traverse between indices i,j if gcd(nums[i], nums[j]) > 1.
 * Check if all indices are reachable from each other (transitively).
 * 
 * Approach: For each number, factorize it. Union index with each prime factor.
 * Use a map from prime -> first index seen. All indices sharing a prime get unioned.
 * 
 * Time: O(n * sqrt(max_val) * α(n)), Space: O(n + max_val)
 * 
 * Production Analogy: Service compatibility graph - services that share a common
 * protocol/interface can communicate. Check if all services form one connected mesh.
 */
public class Problem26_GreatestCommonDivisorTraversal {
    
    int[] parent, rank;
    
    public boolean canTraverseAllPairs(int[] nums) {
        int n = nums.length;
        if (n == 1) return true;
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        Map<Integer, Integer> primeToIndex = new HashMap<>();
        
        for (int i = 0; i < n; i++) {
            if (nums[i] == 1) return false; // 1 has no prime factors, can't connect
            int val = nums[i];
            for (int p = 2; p * p <= val; p++) {
                if (val % p == 0) {
                    if (primeToIndex.containsKey(p)) union(i, primeToIndex.get(p));
                    else primeToIndex.put(p, i);
                    while (val % p == 0) val /= p;
                }
            }
            if (val > 1) {
                if (primeToIndex.containsKey(val)) union(i, primeToIndex.get(val));
                else primeToIndex.put(val, i);
            }
        }
        
        int root = find(0);
        for (int i = 1; i < n; i++) if (find(i) != root) return false;
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
    }
    
    public static void main(String[] args) {
        Problem26_GreatestCommonDivisorTraversal sol = new Problem26_GreatestCommonDivisorTraversal();
        System.out.println(sol.canTraverseAllPairs(new int[]{2,3,6})); // true
        System.out.println(sol.canTraverseAllPairs(new int[]{3,9,5})); // false
        System.out.println(sol.canTraverseAllPairs(new int[]{4,3,12,8})); // true
    }
}

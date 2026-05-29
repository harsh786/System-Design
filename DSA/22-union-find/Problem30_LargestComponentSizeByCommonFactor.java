import java.util.*;

/**
 * Problem 30: Largest Component Size by Common Factor (LeetCode 952)
 * 
 * Given array nums, connect i and j if gcd(nums[i], nums[j]) > 1.
 * Find largest connected component size.
 * 
 * Approach: For each number, find its prime factors. Union the number's index
 * with all indices sharing a prime factor.
 * 
 * Time: O(n * sqrt(max) * α(n)), Space: O(n + max)
 * 
 * Production Analogy: Finding largest cluster of interoperable services
 * where services sharing a common protocol can communicate.
 */
public class Problem30_LargestComponentSizeByCommonFactor {
    
    int[] parent, rank, size;
    
    public int largestComponentSize(int[] nums) {
        int n = nums.length;
        parent = new int[n]; rank = new int[n]; size = new int[n];
        for (int i = 0; i < n; i++) { parent[i] = i; size[i] = 1; }
        
        Map<Integer, Integer> primeToIndex = new HashMap<>();
        
        for (int i = 0; i < n; i++) {
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
        
        int max = 1;
        for (int s : size) max = Math.max(max, s);
        return max;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        if (rank[px] < rank[py]) { parent[px] = py; size[py] += size[px]; }
        else if (rank[px] > rank[py]) { parent[py] = px; size[px] += size[py]; }
        else { parent[py] = px; size[px] += size[py]; rank[px]++; }
    }
    
    public static void main(String[] args) {
        Problem30_LargestComponentSizeByCommonFactor sol = new Problem30_LargestComponentSizeByCommonFactor();
        System.out.println(sol.largestComponentSize(new int[]{4,6,15,35})); // 4
        
        sol = new Problem30_LargestComponentSizeByCommonFactor();
        System.out.println(sol.largestComponentSize(new int[]{20,50,9,63})); // 2
    }
}

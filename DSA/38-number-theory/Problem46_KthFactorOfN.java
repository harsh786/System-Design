package numbertheory;

/**
 * Problem 46: Kth Factor of N (LeetCode 1492)
 * 
 * Approach: Check divisors up to sqrt(n), store small and large factors.
 * 
 * Time Complexity: O(sqrt(n))
 * Space Complexity: O(sqrt(n))
 */
public class Problem46_KthFactorOfN {
    
    public int kthFactor(int n, int k) {
        java.util.List<Integer> small = new java.util.ArrayList<>();
        java.util.List<Integer> large = new java.util.ArrayList<>();
        for (int i = 1; i * i <= n; i++) {
            if (n % i == 0) {
                small.add(i);
                if (i != n / i) large.add(n / i);
            }
        }
        int total = small.size() + large.size();
        if (k > total) return -1;
        if (k <= small.size()) return small.get(k - 1);
        return large.get(total - k);
    }
    
    public static void main(String[] args) {
        Problem46_KthFactorOfN sol = new Problem46_KthFactorOfN();
        System.out.println(sol.kthFactor(12, 3)); // 3
        System.out.println(sol.kthFactor(4, 4));  // -1
    }
}

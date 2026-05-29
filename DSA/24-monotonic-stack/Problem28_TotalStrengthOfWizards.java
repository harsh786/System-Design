import java.util.*;

/**
 * Problem 28: Total Strength of Wizards (LeetCode 2281)
 * 
 * For each subarray, strength = min(subarray) * sum(subarray). Find total of all.
 * 
 * Approach: For each element as minimum, find contribution using prefix of prefix sums
 * and monotonic stack for boundaries.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Calculating total cost across all possible team configurations
 * where cost = weakest_member * total_output.
 */
public class Problem28_TotalStrengthOfWizards {
    
    public int totalStrength(int[] strength) {
        int n = strength.length;
        long MOD = 1_000_000_007;
        
        // prefix sum and prefix of prefix sum
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = (prefix[i] + strength[i]) % MOD;
        long[] prefixPrefix = new long[n + 2];
        for (int i = 0; i <= n; i++) prefixPrefix[i + 1] = (prefixPrefix[i] + prefix[i]) % MOD;
        
        int[] left = new int[n], right = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && strength[stack.peek()] >= strength[i]) stack.pop();
            left[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(i);
        }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && strength[stack.peek()] > strength[i]) stack.pop();
            right[i] = stack.isEmpty() ? n : stack.peek();
            stack.push(i);
        }
        
        long ans = 0;
        for (int i = 0; i < n; i++) {
            int l = left[i], r = right[i];
            // Sum of all subarray sums where strength[i] is minimum
            long rightSum = (prefixPrefix[r + 1] - prefixPrefix[i + 1] + MOD) % MOD * ((i - l) % MOD) % MOD;
            long leftSum = (prefixPrefix[i + 1] - prefixPrefix[l + 1] + MOD) % MOD * ((r - i) % MOD) % MOD;
            ans = (ans + strength[i] % MOD * ((rightSum - leftSum + MOD) % MOD)) % MOD;
        }
        return (int) ans;
    }
    
    public static void main(String[] args) {
        Problem28_TotalStrengthOfWizards sol = new Problem28_TotalStrengthOfWizards();
        System.out.println(sol.totalStrength(new int[]{1,3,1,2})); // 44
        System.out.println(sol.totalStrength(new int[]{5,4,6}));   // 213
    }
}

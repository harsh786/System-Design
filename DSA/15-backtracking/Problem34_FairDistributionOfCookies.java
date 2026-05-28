import java.util.*;

/**
 * Problem 34: Fair Distribution of Cookies (LeetCode 2305)
 * 
 * Distribute n bags of cookies to k children, minimize the maximum total cookies any child gets.
 * 
 * Search Tree:
 * - For each bag, assign it to one of k children
 * - Track max among children; minimize it
 * 
 * Pruning Strategy:
 * - Sort bags descending for tighter early bounds
 * - If current max already >= best known answer, prune
 * - Skip children with same current total (symmetry breaking)
 * 
 * Time Complexity: O(k^n) worst case, much better with pruning
 * Space Complexity: O(n + k)
 * 
 * Production Analogy:
 * - Load balancing: distributing batch jobs across k workers to minimize max latency.
 */
public class Problem34_FairDistributionOfCookies {

    private int result;

    public int distributeCookies(int[] cookies, int k) {
        result = Integer.MAX_VALUE;
        Arrays.sort(cookies);
        // reverse for better pruning
        for (int i = 0, j = cookies.length - 1; i < j; i++, j--) {
            int t = cookies[i]; cookies[i] = cookies[j]; cookies[j] = t;
        }
        backtrack(cookies, new int[k], 0);
        return result;
    }

    private void backtrack(int[] cookies, int[] children, int idx) {
        if (idx == cookies.length) {
            int max = 0;
            for (int c : children) max = Math.max(max, c);
            result = Math.min(result, max);
            return;
        }
        Set<Integer> seen = new HashSet<>();
        for (int i = 0; i < children.length; i++) {
            if (children[i] + cookies[idx] >= result) continue; // pruning
            if (!seen.add(children[i])) continue; // symmetry breaking
            children[i] += cookies[idx];
            backtrack(cookies, children, idx + 1);
            children[i] -= cookies[idx];
        }
    }

    public static void main(String[] args) {
        Problem34_FairDistributionOfCookies sol = new Problem34_FairDistributionOfCookies();

        System.out.println(sol.distributeCookies(new int[]{8,15,10,20,8}, 2)); // 31
        System.out.println(sol.distributeCookies(new int[]{6,1,3,2,2,4,1,2}, 3)); // 7
    }
}

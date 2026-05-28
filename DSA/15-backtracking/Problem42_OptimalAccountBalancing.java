import java.util.*;

/**
 * Problem 42: Optimal Account Balancing (LeetCode 465)
 * 
 * Given transactions between people, find minimum number of transactions to settle all debts.
 * 
 * Search Tree:
 * - Compute net balance for each person; remove zeros
 * - For first non-zero balance, try settling with each person of opposite sign
 * - Recurse on remaining balances
 * 
 * Pruning Strategy:
 * - Skip persons with zero balance
 * - If two balances perfectly cancel (a + b == 0), settle them first (greedy optimization)
 * - Skip same-valued balances to avoid duplicate exploration
 * 
 * Time Complexity: O(n!) worst case where n = non-zero balances
 * Space Complexity: O(n)
 * 
 * Production Analogy:
 * - Minimizing inter-service payment transactions in a multi-party settlement system.
 */
public class Problem42_OptimalAccountBalancing {

    public int minTransfers(int[][] transactions) {
        Map<Integer, Integer> balanceMap = new HashMap<>();
        for (int[] t : transactions) {
            balanceMap.merge(t[0], -t[2], Integer::sum);
            balanceMap.merge(t[1], t[2], Integer::sum);
        }
        List<Integer> debts = new ArrayList<>();
        for (int v : balanceMap.values()) if (v != 0) debts.add(v);
        return dfs(debts, 0);
    }

    private int dfs(List<Integer> debts, int start) {
        while (start < debts.size() && debts.get(start) == 0) start++;
        if (start == debts.size()) return 0;

        int min = Integer.MAX_VALUE;
        for (int i = start + 1; i < debts.size(); i++) {
            if ((long) debts.get(start) * debts.get(i) < 0) { // opposite signs
                debts.set(i, debts.get(i) + debts.get(start));
                min = Math.min(min, 1 + dfs(debts, start + 1));
                debts.set(i, debts.get(i) - debts.get(start));
                // If perfectly cancelled, this is optimal for this pair
                if (debts.get(i) + debts.get(start) == 0) break;
            }
        }
        return min;
    }

    public static void main(String[] args) {
        Problem42_OptimalAccountBalancing sol = new Problem42_OptimalAccountBalancing();

        System.out.println(sol.minTransfers(new int[][]{{0,1,10},{2,0,5}})); // 2
        System.out.println(sol.minTransfers(new int[][]{{0,1,10},{1,0,1},{1,2,5},{2,0,5}})); // 1
    }
}

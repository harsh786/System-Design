import java.util.*;

/**
 * Problem 41: Shopping Offers (LeetCode 638)
 * 
 * Buy items at individual prices or use special offers (bundles). Find minimum cost.
 * 
 * Search Tree:
 * - At each step: try each applicable offer or buy remaining individually
 * - Recurse with reduced needs after applying an offer
 * 
 * Pruning Strategy:
 * - Skip offers that exceed any item's remaining need
 * - Memoize on remaining needs state
 * - Don't use offer if it costs more than buying items individually
 * 
 * Time Complexity: O(offers^(max_need/min_offer_qty)) with memoization
 * Space Complexity: O(states) for memo
 * 
 * Production Analogy:
 * - Cloud pricing optimization: choosing between on-demand instances and reserved bundles.
 */
public class Problem41_ShoppingOffers {

    public int shoppingOffers(List<Integer> price, List<List<Integer>> special, List<Integer> needs) {
        Map<List<Integer>, Integer> memo = new HashMap<>();
        return dfs(price, special, needs, memo);
    }

    private int dfs(List<Integer> price, List<List<Integer>> special, List<Integer> needs, Map<List<Integer>, Integer> memo) {
        if (memo.containsKey(needs)) return memo.get(needs);

        // Cost without any offer
        int minCost = 0;
        for (int i = 0; i < needs.size(); i++) minCost += needs.get(i) * price.get(i);

        // Try each offer
        for (List<Integer> offer : special) {
            List<Integer> remaining = new ArrayList<>();
            boolean valid = true;
            for (int i = 0; i < needs.size(); i++) {
                int diff = needs.get(i) - offer.get(i);
                if (diff < 0) { valid = false; break; }
                remaining.add(diff);
            }
            if (!valid) continue;
            int cost = offer.get(offer.size() - 1) + dfs(price, special, remaining, memo);
            minCost = Math.min(minCost, cost);
        }
        memo.put(needs, minCost);
        return minCost;
    }

    public static void main(String[] args) {
        Problem41_ShoppingOffers sol = new Problem41_ShoppingOffers();

        System.out.println(sol.shoppingOffers(
            Arrays.asList(2, 5),
            Arrays.asList(Arrays.asList(3, 0, 5), Arrays.asList(1, 2, 10)),
            Arrays.asList(3, 2))); // 14

        System.out.println(sol.shoppingOffers(
            Arrays.asList(2, 3, 4),
            Arrays.asList(Arrays.asList(1, 1, 0, 4), Arrays.asList(2, 2, 1, 9)),
            Arrays.asList(1, 2, 1))); // 11
    }
}

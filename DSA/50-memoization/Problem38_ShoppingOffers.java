import java.util.*;

public class Problem38_ShoppingOffers {
    private Map<List<Integer>, Integer> memo = new HashMap<>();

    public int shoppingOffers(List<Integer> price, List<List<Integer>> special, List<Integer> needs) {
        return helper(price, special, needs);
    }

    private int helper(List<Integer> price, List<List<Integer>> special, List<Integer> needs) {
        if (memo.containsKey(needs)) return memo.get(needs);
        int cost = 0;
        for (int i = 0; i < needs.size(); i++) cost += needs.get(i) * price.get(i);
        for (List<Integer> offer : special) {
            List<Integer> next = new ArrayList<>();
            boolean valid = true;
            for (int i = 0; i < needs.size(); i++) {
                if (needs.get(i) < offer.get(i)) { valid = false; break; }
                next.add(needs.get(i) - offer.get(i));
            }
            if (valid) cost = Math.min(cost, offer.get(needs.size()) + helper(price, special, next));
        }
        memo.put(needs, cost);
        return cost;
    }

    public static void main(String[] args) {
        Problem38_ShoppingOffers sol = new Problem38_ShoppingOffers();
        List<Integer> price = Arrays.asList(2, 5);
        List<List<Integer>> special = Arrays.asList(Arrays.asList(3, 0, 5), Arrays.asList(1, 2, 10));
        List<Integer> needs = Arrays.asList(3, 2);
        System.out.println(sol.shoppingOffers(price, special, needs)); // 14
    }
}

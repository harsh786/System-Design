import java.util.*;

/**
 * Problem 40: Final Prices With a Special Discount in a Shop (LeetCode 1475)
 * 
 * For each item, find next item with price <= current as discount.
 * 
 * Approach: Monotonic stack - find next smaller or equal element.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like applying discount rules in e-commerce where each item's
 * price is reduced by the first qualifying discount found in sequence.
 */
public class Problem40_FinalPricesWithDiscount {

    public static int[] finalPrices(int[] prices) {
        int[] result = prices.clone();
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i < prices.length; i++) {
            while (!stack.isEmpty() && prices[stack.peek()] >= prices[i]) {
                result[stack.pop()] -= prices[i];
            }
            stack.push(i);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(finalPrices(new int[]{8,4,6,2,3}))); // [4,2,4,2,3]
        System.out.println(Arrays.toString(finalPrices(new int[]{1,2,3,4,5}))); // [1,2,3,4,5]
        System.out.println(Arrays.toString(finalPrices(new int[]{10,1,1,6}))); // [9,0,1,6]
    }
}

import java.util.*;

/**
 * Problem 11: Final Prices With Special Discount (LeetCode 1475)
 * 
 * For each item, find the first item to its right with price <= current. Subtract it.
 * 
 * Monotonic Invariant: Increasing stack. When a smaller/equal element arrives,
 * pop and apply discount.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Pricing engine - apply first available coupon that doesn't
 * exceed item value.
 */
public class Problem11_FinalPricesWithSpecialDiscount {
    
    public int[] finalPrices(int[] prices) {
        int n = prices.length;
        int[] result = prices.clone();
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && prices[stack.peek()] >= prices[i]) {
                int idx = stack.pop();
                result[idx] = prices[idx] - prices[i];
            }
            stack.push(i);
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem11_FinalPricesWithSpecialDiscount sol = new Problem11_FinalPricesWithSpecialDiscount();
        
        System.out.println(Arrays.toString(sol.finalPrices(new int[]{8,4,6,2,3}))); // [4,2,4,2,3]
        System.out.println(Arrays.toString(sol.finalPrices(new int[]{1,2,3,4,5}))); // [1,2,3,4,5]
        System.out.println(Arrays.toString(sol.finalPrices(new int[]{10,1,1,6})));  // [9,0,1,6]
    }
}

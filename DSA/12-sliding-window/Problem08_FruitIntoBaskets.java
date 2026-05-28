import java.util.*;
/**
 * Problem 8: Fruit Into Baskets (LeetCode 904)
 * 
 * Approach: Longest subarray with at most 2 distinct elements.
 * Window invariant: at most 2 distinct fruit types in window.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like maintaining connections to at most K different
 * downstream services in a connection pool window.
 */
public class Problem08_FruitIntoBaskets {
    public static int totalFruit(int[] fruits) {
        Map<Integer, Integer> basket = new HashMap<>();
        int left = 0, maxLen = 0;
        for (int right = 0; right < fruits.length; right++) {
            basket.merge(fruits[right], 1, Integer::sum);
            while (basket.size() > 2) {
                int lf = fruits[left];
                basket.merge(lf, -1, Integer::sum);
                if (basket.get(lf) == 0) basket.remove(lf);
                left++;
            }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(totalFruit(new int[]{1,2,1}));       // 3
        System.out.println(totalFruit(new int[]{0,1,2,2}));     // 3
        System.out.println(totalFruit(new int[]{1,2,3,2,2}));   // 4
        System.out.println(totalFruit(new int[]{3,3,3,1,2,1,1,2,3,3,4})); // 5
    }
}

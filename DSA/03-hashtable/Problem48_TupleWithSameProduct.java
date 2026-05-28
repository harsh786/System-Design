import java.util.*;

/**
 * Problem 48: Tuple with Same Product
 * Count tuples (a,b,c,d) where a*b = c*d. All elements distinct.
 *
 * Approach: Count all pair products. For each product with count c, tuples = c*(c-1)/2 * 8.
 * (8 because each pair of pairs can be arranged in 8 ways)
 *
 * Time Complexity: O(n^2)
 * Space Complexity: O(n^2)
 *
 * Production Analogy: Like finding equivalent load distributions in a cluster -
 * pairs of (server, traffic) assignments that yield the same total throughput.
 */
public class Problem48_TupleWithSameProduct {
    public int tupleSameProduct(int[] nums) {
        Map<Integer, Integer> productCount = new HashMap<>();
        for (int i = 0; i < nums.length; i++)
            for (int j = i + 1; j < nums.length; j++)
                productCount.merge(nums[i] * nums[j], 1, Integer::sum);
        int total = 0;
        for (int count : productCount.values())
            total += count * (count - 1) / 2 * 8;
        return total;
    }

    public static void main(String[] args) {
        Problem48_TupleWithSameProduct sol = new Problem48_TupleWithSameProduct();
        System.out.println(sol.tupleSameProduct(new int[]{2,3,4,6})); // 8
        System.out.println(sol.tupleSameProduct(new int[]{1,2,4,5,10})); // 16
    }
}

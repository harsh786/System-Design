/**
 * Problem: Tuple with Same Product (LeetCode 1726)
 * Approach: Count pairs with same product, each pair of pairs gives 8 tuples
 * Complexity: O(n^2) time, O(n^2) space
 * Production Analogy: Finding equivalent transformations in data pipelines
 */
import java.util.*;
public class Problem37_TupleWithSameProduct {
    public int tupleSameProduct(int[] nums) {
        Map<Integer, Integer> productCount = new HashMap<>();
        for (int i = 0; i < nums.length; i++)
            for (int j = i+1; j < nums.length; j++)
                productCount.merge(nums[i]*nums[j], 1, Integer::sum);
        int count = 0;
        for (int v : productCount.values()) count += v * (v-1) / 2 * 8;
        return count;
    }
    public static void main(String[] args) {
        System.out.println(new Problem37_TupleWithSameProduct().tupleSameProduct(new int[]{2,3,4,6})); // 8
    }
}

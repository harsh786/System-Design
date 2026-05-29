/**
 * Problem 29: Bitwise ORs of Subarrays
 * Return number of distinct OR results of all subarrays.
 * 
 * Approach: For each position, maintain set of all OR values ending here.
 * OR is monotonically increasing and has at most 32 distinct values per position.
 * Time: O(32n), Space: O(32n)
 * 
 * Production Analogy: Computing all possible combined capability sets from sequential services.
 */
import java.util.*;

public class Problem29_BitwiseORsOfSubarrays {
    public static int subarrayBitwiseORs(int[] arr) {
        Set<Integer> result = new HashSet<>();
        Set<Integer> prev = new HashSet<>();
        for (int num : arr) {
            Set<Integer> curr = new HashSet<>();
            curr.add(num);
            for (int p : prev) curr.add(p | num);
            result.addAll(curr);
            prev = curr;
        }
        return result.size();
    }

    public static void main(String[] args) {
        System.out.println(subarrayBitwiseORs(new int[]{0})); // 1
        System.out.println(subarrayBitwiseORs(new int[]{1,1,2})); // 3
        System.out.println(subarrayBitwiseORs(new int[]{1,2,4})); // 6
    }
}

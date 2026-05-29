/**
 * Problem 6: Plus One
 * Given a large integer represented as an array of digits, increment by one.
 *
 * Approach: Start from the end, handle carry propagation.
 * Time Complexity: O(n)
 * Space Complexity: O(n) worst case (e.g., 999 -> 1000)
 *
 * Production Analogy: Like incrementing version counters or sequence numbers
 * stored as arrays in distributed systems.
 */
import java.util.Arrays;

public class Problem06_PlusOne {

    public static int[] plusOne(int[] digits) {
        for (int i = digits.length - 1; i >= 0; i--) {
            if (digits[i] < 9) {
                digits[i]++;
                return digits;
            }
            digits[i] = 0;
        }
        // All 9s case
        int[] result = new int[digits.length + 1];
        result[0] = 1;
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(plusOne(new int[]{1,2,3})));   // [1,2,4]
        System.out.println(Arrays.toString(plusOne(new int[]{9,9,9})));   // [1,0,0,0]
        System.out.println(Arrays.toString(plusOne(new int[]{0})));       // [1]
        System.out.println(Arrays.toString(plusOne(new int[]{9})));       // [1,0]
    }
}

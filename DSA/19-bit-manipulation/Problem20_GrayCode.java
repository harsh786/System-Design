/**
 * Problem 20: Gray Code
 * Generate n-bit Gray code sequence (adjacent numbers differ by 1 bit).
 * 
 * Approach: Gray code formula: i ^ (i >> 1)
 * Time: O(2^n), Space: O(2^n)
 * 
 * Production Analogy: Error-minimizing encoding in rotary encoders / state machines.
 */
import java.util.*;

public class Problem20_GrayCode {
    public static List<Integer> grayCode(int n) {
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < (1 << n); i++) {
            result.add(i ^ (i >> 1));
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(grayCode(2)); // [0,1,3,2]
        System.out.println(grayCode(3)); // [0,1,3,2,6,7,5,4]
        System.out.println(grayCode(1)); // [0,1]
    }
}

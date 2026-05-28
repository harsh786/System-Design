/**
 * Problem 19: Maximum Swap (LeetCode 670)
 *
 * Greedy Choice: Swap leftmost digit with the rightmost larger digit that appears later.
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Single priority inversion fix in a task queue for maximum throughput gain.
 */
public class Problem19_MaximumSwap {
    
    public static int maximumSwap(int num) {
        char[] digits = String.valueOf(num).toCharArray();
        int[] last = new int[10];
        for (int i = 0; i < digits.length; i++) last[digits[i] - '0'] = i;
        for (int i = 0; i < digits.length; i++) {
            for (int d = 9; d > digits[i] - '0'; d--) {
                if (last[d] > i) {
                    char tmp = digits[i];
                    digits[i] = digits[last[d]];
                    digits[last[d]] = tmp;
                    return Integer.parseInt(new String(digits));
                }
            }
        }
        return num;
    }
    
    public static void main(String[] args) {
        System.out.println(maximumSwap(2736)); // 7236
        System.out.println(maximumSwap(9973)); // 9973
        System.out.println(maximumSwap(1993)); // 9913
    }
}

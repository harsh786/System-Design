/**
 * Problem 22: Integer Replacement
 * Given n, reach 1 with minimum ops: if even n/2, if odd n+1 or n-1.
 * 
 * Approach: Greedy with bit inspection. If last 2 bits are 11, prefer +1 (except n=3).
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Optimal step-down scaling of cloud instances to target capacity.
 */
public class Problem22_IntegerReplacement {
    public static int integerReplacement(int n) {
        int count = 0;
        long num = n; // avoid overflow for Integer.MAX_VALUE
        while (num != 1) {
            if ((num & 1) == 0) {
                num >>= 1;
            } else if (num == 3 || (num & 3) == 1) {
                num--;
            } else {
                num++;
            }
            count++;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(integerReplacement(8)); // 3
        System.out.println(integerReplacement(7)); // 4
        System.out.println(integerReplacement(1)); // 0
        System.out.println(integerReplacement(Integer.MAX_VALUE)); // 32
    }
}

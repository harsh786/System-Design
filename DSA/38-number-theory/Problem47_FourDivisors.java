package numbertheory;

/**
 * Problem 47: Four Divisors (LeetCode 1390)
 * 
 * Approach: For each number, count divisors. If exactly 4, add sum of divisors.
 * 
 * Time Complexity: O(n * sqrt(max_val))
 * Space Complexity: O(1)
 */
public class Problem47_FourDivisors {
    
    public int sumFourDivisors(int[] nums) {
        int total = 0;
        for (int n : nums) {
            int count = 0, sum = 0;
            for (int i = 1; (long) i * i <= n; i++) {
                if (n % i == 0) {
                    count++; sum += i;
                    if (i != n / i) { count++; sum += n / i; }
                }
                if (count > 4) break;
            }
            if (count == 4) total += sum;
        }
        return total;
    }
    
    public static void main(String[] args) {
        Problem47_FourDivisors sol = new Problem47_FourDivisors();
        System.out.println(sol.sumFourDivisors(new int[]{21, 4, 7})); // 32 (21: 1+3+7+21)
    }
}

package numbertheory;

/**
 * Problem 42: Sum of Square Numbers (LeetCode 633)
 * 
 * Approach: Two pointers: a=0, b=sqrt(c). Move inward.
 * 
 * Time Complexity: O(sqrt(c))
 * Space Complexity: O(1)
 */
public class Problem42_SumOfSquareNumbers {
    
    public boolean judgeSquareSum(int c) {
        long lo = 0, hi = (long) Math.sqrt(c);
        while (lo <= hi) {
            long sum = lo * lo + hi * hi;
            if (sum == c) return true;
            if (sum < c) lo++;
            else hi--;
        }
        return false;
    }
    
    public static void main(String[] args) {
        Problem42_SumOfSquareNumbers sol = new Problem42_SumOfSquareNumbers();
        System.out.println(sol.judgeSquareSum(5));  // true (1+4)
        System.out.println(sol.judgeSquareSum(3));  // false
    }
}

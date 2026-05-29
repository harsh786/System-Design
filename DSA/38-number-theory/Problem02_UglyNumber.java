package numbertheory;

/**
 * Problem 2: Ugly Number (LeetCode 263)
 * 
 * Approach: Divide by 2, 3, 5 until can't. If result is 1, it's ugly.
 * 
 * Time Complexity: O(log n)
 * Space Complexity: O(1)
 */
public class Problem02_UglyNumber {
    
    public boolean isUgly(int n) {
        if (n <= 0) return false;
        for (int f : new int[]{2, 3, 5})
            while (n % f == 0) n /= f;
        return n == 1;
    }
    
    public static void main(String[] args) {
        Problem02_UglyNumber sol = new Problem02_UglyNumber();
        System.out.println(sol.isUgly(6));  // true
        System.out.println(sol.isUgly(14)); // false
    }
}

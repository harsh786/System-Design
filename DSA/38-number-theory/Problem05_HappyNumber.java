package numbertheory;

/**
 * Problem 5: Happy Number (LeetCode 202)
 * 
 * Approach: Floyd's cycle detection on digit-square-sum sequence.
 * 
 * Time Complexity: O(log n) per step
 * Space Complexity: O(1)
 */
public class Problem05_HappyNumber {
    
    private int next(int n) {
        int sum = 0;
        while (n > 0) { int d = n % 10; sum += d * d; n /= 10; }
        return sum;
    }
    
    public boolean isHappy(int n) {
        int slow = n, fast = next(n);
        while (fast != 1 && slow != fast) { slow = next(slow); fast = next(next(fast)); }
        return fast == 1;
    }
    
    public static void main(String[] args) {
        Problem05_HappyNumber sol = new Problem05_HappyNumber();
        System.out.println(sol.isHappy(19)); // true
        System.out.println(sol.isHappy(2));  // false
    }
}

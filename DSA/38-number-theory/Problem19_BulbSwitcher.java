package numbertheory;

/**
 * Problem 19: Bulb Switcher (LeetCode 319)
 * 
 * Approach: A bulb ends ON iff toggled odd number of times = has odd number of divisors = perfect square.
 * Answer = floor(sqrt(n)).
 * 
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 */
public class Problem19_BulbSwitcher {
    
    public int bulbSwitch(int n) { return (int) Math.sqrt(n); }
    
    public static void main(String[] args) {
        Problem19_BulbSwitcher sol = new Problem19_BulbSwitcher();
        System.out.println(sol.bulbSwitch(3));  // 1
        System.out.println(sol.bulbSwitch(10)); // 3
    }
}

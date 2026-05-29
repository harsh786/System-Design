/**
 * Problem 21: Bulb Switcher
 * n bulbs toggled in n rounds (round i toggles every i-th bulb). Count ON bulbs.
 *
 * Approach: A bulb stays ON only if toggled odd number of times = perfect square position.
 * Answer is floor(sqrt(n)).
 * Time Complexity: O(1)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like determining which feature flags remain active after
 * multiple toggle operations - only those with odd divisor count stay flipped.
 */
public class Problem21_BulbSwitcher {

    public static int bulbSwitch(int n) {
        return (int) Math.sqrt(n);
    }

    public static void main(String[] args) {
        System.out.println(bulbSwitch(3));   // 1
        System.out.println(bulbSwitch(0));   // 0
        System.out.println(bulbSwitch(1));   // 1
        System.out.println(bulbSwitch(100)); // 10
    }
}

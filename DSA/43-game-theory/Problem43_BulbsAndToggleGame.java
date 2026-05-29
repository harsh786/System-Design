import java.util.*;

public class Problem43_BulbsAndToggleGame {
    // Bulbs Toggle Game: n bulbs, player toggles bulb i and all multiples of i.
    // Player who makes all bulbs off wins. First player wins iff n is a perfect square.
    // (Each bulb i is toggled by its divisors; perfect squares have odd # divisors)
    
    public boolean firstPlayerWins(int n) {
        // Number of bulbs that end up on = number of perfect squares <= n
        int sqrtN = (int) Math.sqrt(n);
        return sqrtN * sqrtN == n || sqrtN > 0;
    }
    
    // Simpler version: 319. Bulb Switcher - after n rounds, count bulbs on
    public int bulbSwitch(int n) {
        return (int) Math.sqrt(n);
    }
    
    public static void main(String[] args) {
        Problem43_BulbsAndToggleGame sol = new Problem43_BulbsAndToggleGame();
        System.out.println(sol.bulbSwitch(3));  // 1
        System.out.println(sol.bulbSwitch(16)); // 4
        System.out.println(sol.bulbSwitch(99)); // 9
    }
}

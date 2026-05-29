import java.util.*;

public class Problem48_MockTurtles {
    // Mock Turtles: Variant of Turning Turtles with odious numbers.
    // Row of coins (face up/down). Turn over any coin and optionally one to its left.
    // Position is losing if XOR of all "odious" positions is 0.
    // Odious number: has odd number of 1s in binary.
    
    public boolean isOdious(int n) {
        return Integer.bitCount(n) % 2 == 1;
    }
    
    // Mock Turtle values: for coin at position i, value = 2i+1 if odious, else 2i
    // Actually the Mock Turtles game uses "odious numbers" as Grundy values
    public int grundyMockTurtle(int pos) {
        int val = 2 * pos + 1;
        if (isOdious(val)) return val;
        // Toggle lowest bit to make odious
        return val ^ 1;
    }
    
    public boolean firstPlayerWins(boolean[] coins) {
        int xor = 0;
        for (int i = 0; i < coins.length; i++) {
            if (coins[i]) { // face up = active
                xor ^= grundyMockTurtle(i);
            }
        }
        return xor != 0;
    }
    
    public static void main(String[] args) {
        Problem48_MockTurtles sol = new Problem48_MockTurtles();
        boolean[] coins = {true, false, true, true}; // positions 0,2,3 are face-up
        System.out.println("First player wins: " + sol.firstPlayerWins(coins));
        System.out.println("Is 7 odious? " + sol.isOdious(7)); // true (111 -> 3 ones)
    }
}

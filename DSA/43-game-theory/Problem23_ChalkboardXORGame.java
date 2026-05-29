import java.util.*;

public class Problem23_ChalkboardXORGame {
    // 810. Chalkboard XOR Game: Players erase one number. If XOR becomes 0, eraser loses.
    // Alice goes first. Return true if Alice wins.
    // Key insight: Alice wins if XOR==0 initially OR array length is even.
    
    public boolean xorGame(int[] nums) {
        int xor = 0;
        for (int n : nums) xor ^= n;
        return xor == 0 || nums.length % 2 == 0;
    }
    
    public static void main(String[] args) {
        Problem23_ChalkboardXORGame sol = new Problem23_ChalkboardXORGame();
        System.out.println(sol.xorGame(new int[]{1,1,2})); // false
        System.out.println(sol.xorGame(new int[]{1,2,3})); // true (even? no, xor=0? 1^2^3=0? yes)
    }
}

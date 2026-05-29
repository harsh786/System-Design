import java.util.*;

public class Problem30_WythoffGame {
    // Wythoff's Game: Two piles. Remove any number from one pile, or equal from both.
    // Losing positions (cold positions): (floor(k*phi), floor(k*phi^2)) for k=0,1,2,...
    // phi = (1+sqrt(5))/2
    
    public boolean isWinning(int a, int b) {
        if (a > b) { int t = a; a = b; b = t; }
        double phi = (1 + Math.sqrt(5)) / 2;
        int k = b - a;
        int coldA = (int)(k * phi);
        return a != coldA;
    }
    
    public static void main(String[] args) {
        Problem30_WythoffGame sol = new Problem30_WythoffGame();
        // Cold positions: (0,0),(1,2),(3,5),(4,7),(6,10),...
        System.out.println("(1,2): " + sol.isWinning(1, 2)); // false (cold)
        System.out.println("(3,5): " + sol.isWinning(3, 5)); // false (cold)
        System.out.println("(2,3): " + sol.isWinning(2, 3)); // true (hot)
    }
}

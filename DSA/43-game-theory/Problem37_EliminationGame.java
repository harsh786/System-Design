import java.util.*;

public class Problem37_EliminationGame {
    // 390. Elimination Game: Numbers 1..n. Alternately eliminate from left then right.
    // Return last remaining number.
    
    public int lastRemaining(int n) {
        int head = 1, step = 1, remaining = n;
        boolean left = true;
        while (remaining > 1) {
            if (left || remaining % 2 == 1) head += step;
            remaining /= 2;
            step *= 2;
            left = !left;
        }
        return head;
    }
    
    public static void main(String[] args) {
        Problem37_EliminationGame sol = new Problem37_EliminationGame();
        System.out.println(sol.lastRemaining(9));  // 6
        System.out.println(sol.lastRemaining(1));  // 1
    }
}

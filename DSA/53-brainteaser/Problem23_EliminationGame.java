public class Problem23_EliminationGame {
    // LC 390: Eliminate from left then right alternately
    static int lastRemaining(int n) {
        int head = 1, step = 1, remaining = n;
        boolean left = true;
        while (remaining > 1) {
            if (left || remaining % 2 == 1) head += step;
            step *= 2;
            remaining /= 2;
            left = !left;
        }
        return head;
    }
    
    public static void main(String[] args) {
        System.out.println("n=9: " + lastRemaining(9)); // 6
    }
}

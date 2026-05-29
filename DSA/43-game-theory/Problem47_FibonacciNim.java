import java.util.*;

public class Problem47_FibonacciNim {
    // Fibonacci Nim (Wythoff variant): One pile. First player takes 1..n-1.
    // Subsequently, take 1..2*(previous move). Zeckendorf's representation determines winner.
    // First player loses iff n is a Fibonacci number.
    
    public boolean firstPlayerWins(int n) {
        return !isFibonacci(n);
    }
    
    private boolean isFibonacci(int n) {
        int a = 1, b = 2;
        while (b < n) { int t = a + b; a = b; b = t; }
        return b == n || a == n || n == 1;
    }
    
    // Zeckendorf representation
    public List<Integer> zeckendorf(int n) {
        List<Integer> fibs = new ArrayList<>();
        int a = 1, b = 2;
        while (b <= n) { fibs.add(b); int t = a + b; a = b; b = t; }
        fibs.add(0, 1);
        
        List<Integer> rep = new ArrayList<>();
        for (int i = fibs.size() - 1; i >= 0 && n > 0; i--) {
            if (fibs.get(i) <= n) { rep.add(fibs.get(i)); n -= fibs.get(i); }
        }
        return rep;
    }
    
    public static void main(String[] args) {
        Problem47_FibonacciNim sol = new Problem47_FibonacciNim();
        for (int i = 1; i <= 15; i++) {
            System.out.println("n=" + i + ": " + (sol.firstPlayerWins(i) ? "Win" : "Lose")
                + " Zeckendorf: " + sol.zeckendorf(i));
        }
    }
}

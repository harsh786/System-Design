import java.util.*;

public class Problem30_TernarySearchWithOracle {
    // Find maximum of unimodal function
    static double f(double x) { return -(x - 3.5) * (x - 3.5) + 10; }
    
    static double ternarySearch(double lo, double hi) {
        for (int i = 0; i < 100; i++) {
            double m1 = lo + (hi - lo) / 3, m2 = hi - (hi - lo) / 3;
            if (f(m1) < f(m2)) lo = m1; else hi = m2;
        }
        return (lo + hi) / 2;
    }
    
    public static void main(String[] args) {
        double x = ternarySearch(0, 10);
        System.out.printf("Max at x=%.4f, f(x)=%.4f%n", x, f(x));
    }
}

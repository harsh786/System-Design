import java.util.*;

public class Problem47_ABWinnerSearch {
    // Find optimal threshold in A/B test using binary search
    static double[] conversionRates = {0.05,0.08,0.12,0.15,0.18,0.20,0.19,0.17,0.14,0.10};
    
    static double getConversionRate(int pricePoint) { return conversionRates[pricePoint]; }
    
    // Unimodal - find peak using ternary search
    static int findOptimalPrice(int n) {
        int lo = 0, hi = n - 1;
        while (hi - lo > 2) {
            int m1 = lo + (hi - lo) / 3, m2 = hi - (hi - lo) / 3;
            if (getConversionRate(m1) < getConversionRate(m2)) lo = m1;
            else hi = m2;
        }
        int best = lo;
        for (int i = lo; i <= hi; i++)
            if (getConversionRate(i) > getConversionRate(best)) best = i;
        return best;
    }
    
    public static void main(String[] args) {
        int opt = findOptimalPrice(10);
        System.out.println("Optimal price point: " + opt + " rate=" + conversionRates[opt]);
    }
}

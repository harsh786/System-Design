import java.util.*;

/**
 * Problem 1: Implement Rand10 Using Rand7 (LeetCode 470)
 * 
 * Given a function rand7() that generates uniform random in [1,7],
 * implement rand10() generating uniform random in [1,10].
 * 
 * Approach: Generate rand49() using two calls: (rand7()-1)*7 + rand7() gives [1,49]
 * Reject values > 40, use remaining (1-40) mod 10 + 1 for uniform [1,10]
 * 
 * Expected calls to rand7(): ~2.45 per rand10() call
 * P(reject) = 9/49, E[iterations] = 49/40 ≈ 1.225, E[rand7 calls] = 2*49/40 ≈ 2.45
 */
public class Problem01_Rand10UsingRand7 {

    private static Random rand = new Random();
    
    // Given API
    public static int rand7() {
        return rand.nextInt(7) + 1;
    }

    // Solution: rejection sampling
    public static int rand10() {
        while (true) {
            int row = rand7(); // 1-7
            int col = rand7(); // 1-7
            int idx = (row - 1) * 7 + col; // Uniform [1, 49]
            
            if (idx <= 40) {
                return (idx - 1) % 10 + 1; // Uniform [1, 10]
            }
            // Reject idx in [41, 49] and retry
        }
    }

    // Optimized: reuse rejected values
    public static int rand10Optimized() {
        while (true) {
            int a = rand7(), b = rand7();
            int idx = (a - 1) * 7 + b; // [1, 49]
            if (idx <= 40) return (idx - 1) % 10 + 1;
            
            // idx is in [41, 49] → we have rand9() = idx - 40
            a = idx - 40; // [1, 9]
            b = rand7();
            idx = (a - 1) * 7 + b; // [1, 63]
            if (idx <= 60) return (idx - 1) % 10 + 1;
            
            // idx in [61, 63] → rand3() = idx - 60
            a = idx - 60; // [1, 3]
            b = rand7();
            idx = (a - 1) * 7 + b; // [1, 21]
            if (idx <= 20) return (idx - 1) % 10 + 1;
            // Very unlikely to reach here
        }
    }

    public static void main(String[] args) {
        int trials = 1000000;
        int[] freq = new int[11];
        
        for (int i = 0; i < trials; i++) {
            freq[rand10()]++;
        }
        
        System.out.println("LeetCode 470: Rand10 Using Rand7");
        System.out.println("Distribution over " + trials + " trials:");
        for (int i = 1; i <= 10; i++) {
            System.out.printf("  %2d: %d (%.2f%%, expected 10%%)%n", 
                i, freq[i], 100.0 * freq[i] / trials);
        }
    }
}

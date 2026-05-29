import java.util.*;

/**
 * Problem 9: Random Number in Range with Bias Avoidance
 * 
 * Common problem: rand() % n introduces bias when RAND_MAX+1 is not divisible by n.
 * 
 * Example: rand7() % 3 gives {1:3, 2:3, 3:1} - biased!
 * 7/3 = 2 remainder 1, so value 1 appears in 3 out of 7 cases.
 * 
 * Solution: Rejection sampling! Reject values >= n * floor(RAND_MAX/n)
 * to ensure each outcome maps to exactly floor(RAND_MAX/n) inputs.
 * 
 * This is how java.util.Random.nextInt(bound) works internally.
 */
public class Problem09_BiasAvoidance {

    static Random rand = new Random();

    // BIASED: simple modulo
    static int biasedRandom(int randMax, int n) {
        return (rand.nextInt(randMax) % n);
    }

    // UNBIASED: rejection sampling
    static int unbiasedRandom(int randMax, int n) {
        int limit = randMax - (randMax % n); // Largest multiple of n <= randMax
        while (true) {
            int x = rand.nextInt(randMax);
            if (x < limit) return x % n;
            // Reject: x is in the biased tail
        }
    }

    // Demonstrate: implement fair dice (1-6) using rand8 (0-7)
    static int fairDiceFromRand8() {
        // 8 % 6 = 2, so values 6,7 would cause bias
        while (true) {
            int r = rand.nextInt(8); // 0-7
            if (r < 6) return r + 1;  // Reject 6, 7
        }
    }

    // Java's actual approach (from OpenJDK)
    static int nextIntJavaStyle(int bound) {
        // For power-of-2 bounds, simple mask works
        if ((bound & -bound) == bound) {
            return (int)((bound * (long)rand.nextInt(Integer.MAX_VALUE)) >> 31);
        }
        // General case: rejection sampling
        int bits, val;
        do {
            bits = rand.nextInt(Integer.MAX_VALUE);
            val = bits % bound;
        } while (bits - val + (bound - 1) < 0); // Overflow check for rejection
        return val;
    }

    public static void main(String[] args) {
        int trials = 1000000;
        int randMax = 7; // Can produce 0-6
        int n = 5; // Want uniform 0-4
        // Bias: 7%5=2, so 0 and 1 appear with probability 2/7, 2,3,4 with 1/7
        
        System.out.println("Bias Avoidance in Random Number Generation");
        System.out.println("rand7() mod 5:\n");
        
        // Biased
        int[] biasedFreq = new int[n];
        for (int i = 0; i < trials; i++) biasedFreq[biasedRandom(randMax, n)]++;
        
        // Unbiased
        int[] unbiasedFreq = new int[n];
        for (int i = 0; i < trials; i++) unbiasedFreq[unbiasedRandom(randMax, n)]++;
        
        System.out.printf("%-8s %-15s %-15s %-10s%n", "Value", "Biased%", "Unbiased%", "Expected%");
        for (int i = 0; i < n; i++) {
            System.out.printf("%-8d %-15.2f %-15.2f %-10.2f%n", i,
                100.0*biasedFreq[i]/trials, 100.0*unbiasedFreq[i]/trials, 100.0/n);
        }
        
        System.out.println("\nBias is small for this example but significant for crypto!");
        System.out.println("Rejection rate = (randMax % n) / randMax = " + 
            String.format("%.2f%%", 100.0 * (randMax % n) / randMax));
    }
}

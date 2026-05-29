import java.util.*;

/**
 * Problem 1: Reservoir Sampling (k=1)
 * 
 * Select one random element from a stream of unknown length with equal probability.
 * 
 * Algorithm (Algorithm R for k=1):
 * - Keep the first element as the candidate
 * - For the i-th element (1-indexed), replace candidate with probability 1/i
 * 
 * Proof of uniformity:
 * - P(element i is selected) = (1/i) * product of (1 - 1/j) for j = i+1 to n
 *   = (1/i) * (i/(i+1)) * ((i+1)/(i+2)) * ... * ((n-1)/n)
 *   = 1/n (telescoping)
 * 
 * LeetCode 382: Linked List Random Node
 */
public class Problem01_ReservoirSampling {

    private int[] stream;
    private Random rand;

    public Problem01_ReservoirSampling(int[] stream) {
        this.stream = stream;
        this.rand = new Random();
    }

    /**
     * Pick one random element from the stream with equal probability 1/n
     */
    public int pickRandom() {
        int result = stream[0];
        for (int i = 1; i < stream.length; i++) {
            // Replace with probability 1/(i+1)
            if (rand.nextInt(i + 1) == 0) {
                result = stream[i];
            }
        }
        return result;
    }

    public static void main(String[] args) {
        int[] stream = {10, 20, 30, 40, 50};
        Problem01_ReservoirSampling sampler = new Problem01_ReservoirSampling(stream);
        
        // Run many trials to verify uniform distribution
        int trials = 100000;
        Map<Integer, Integer> freq = new HashMap<>();
        for (int t = 0; t < trials; t++) {
            int picked = sampler.pickRandom();
            freq.merge(picked, 1, Integer::sum);
        }
        
        System.out.println("Reservoir Sampling k=1 (stream of 5 elements)");
        System.out.println("Expected frequency: " + (trials / stream.length));
        System.out.println("Actual frequencies after " + trials + " trials:");
        for (int val : stream) {
            System.out.printf("  %d: %d (%.2f%%)%n", val, freq.getOrDefault(val, 0),
                100.0 * freq.getOrDefault(val, 0) / trials);
        }
    }
}

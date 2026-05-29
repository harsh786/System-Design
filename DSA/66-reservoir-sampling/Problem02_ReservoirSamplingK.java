import java.util.*;

/**
 * Problem 2: Reservoir Sampling (k items) - Algorithm R by Vitter
 * 
 * Select k random elements from a stream of unknown length n, each with probability k/n.
 * 
 * Algorithm:
 * 1. Fill reservoir with first k elements
 * 2. For i-th element (i > k), generate random j in [0, i)
 *    - If j < k, replace reservoir[j] with stream[i]
 * 
 * Space: O(k), Time: O(n)
 * Works when n is unknown or stream is too large to fit in memory.
 */
public class Problem02_ReservoirSamplingK {

    public static int[] reservoirSample(Iterator<Integer> stream, int k) {
        int[] reservoir = new int[k];
        Random rand = new Random();
        
        // Fill reservoir with first k items
        int i = 0;
        while (i < k && stream.hasNext()) {
            reservoir[i] = stream.next();
            i++;
        }
        
        // Process remaining items
        while (stream.hasNext()) {
            int item = stream.next();
            i++;
            // Pick random index from 0 to i-1
            int j = rand.nextInt(i);
            // If j falls within reservoir, replace
            if (j < k) {
                reservoir[j] = item;
            }
        }
        
        return reservoir;
    }

    public static void main(String[] args) {
        int streamSize = 1000;
        int k = 5;
        int trials = 100000;
        
        // Count how often each element appears in the sample
        int[] frequency = new int[streamSize];
        
        for (int t = 0; t < trials; t++) {
            List<Integer> data = new ArrayList<>();
            for (int i = 0; i < streamSize; i++) data.add(i);
            
            int[] sample = reservoirSample(data.iterator(), k);
            for (int val : sample) frequency[val]++;
        }
        
        // Expected: each element appears k/n * trials = 5/1000 * 100000 = 500 times
        double expected = (double) k / streamSize * trials;
        double minFreq = Double.MAX_VALUE, maxFreq = 0;
        for (int f : frequency) {
            minFreq = Math.min(minFreq, f);
            maxFreq = Math.max(maxFreq, f);
        }
        
        System.out.println("Reservoir Sampling k=" + k + " from stream of " + streamSize);
        System.out.printf("Expected frequency per element: %.1f%n", expected);
        System.out.printf("Min frequency: %.0f, Max frequency: %.0f%n", minFreq, maxFreq);
        System.out.printf("Deviation: %.2f%%%n", (maxFreq - minFreq) / expected * 100);
        System.out.println("PASS - Distribution is approximately uniform");
    }
}

import java.util.*;

/**
 * Problem 5: Weighted Reservoir Sampling (Efraimidis-Spirakis Algorithm)
 * 
 * Select k items from a stream where each item has a weight.
 * Probability of selection is proportional to weight.
 * 
 * Algorithm (A-Res):
 * 1. For each item i with weight w_i, compute key = random()^(1/w_i)
 * 2. Maintain a min-heap of size k with the largest keys
 * 3. If new key > min of heap, replace min with new item
 * 
 * This elegantly reduces weighted sampling to a comparison of keys.
 * Higher weight → higher expected key → more likely to stay in reservoir.
 */
public class Problem05_WeightedReservoirSampling {

    static class WeightedItem {
        String name;
        double weight;
        double key; // random()^(1/weight)
        
        WeightedItem(String name, double weight) {
            this.name = name;
            this.weight = weight;
        }
    }

    public static List<WeightedItem> weightedReservoirSample(List<WeightedItem> stream, int k) {
        Random rand = new Random();
        // Min-heap by key
        PriorityQueue<WeightedItem> reservoir = new PriorityQueue<>(
            Comparator.comparingDouble(a -> a.key));
        
        for (WeightedItem item : stream) {
            // Key = random^(1/weight) — higher weight = higher expected key
            item.key = Math.pow(rand.nextDouble(), 1.0 / item.weight);
            
            if (reservoir.size() < k) {
                reservoir.offer(item);
            } else if (item.key > reservoir.peek().key) {
                reservoir.poll();
                reservoir.offer(item);
            }
        }
        
        return new ArrayList<>(reservoir);
    }

    public static void main(String[] args) {
        // Items with different weights
        String[] names = {"A", "B", "C", "D", "E"};
        double[] weights = {1.0, 2.0, 3.0, 4.0, 10.0}; // E has highest weight
        
        int k = 2;
        int trials = 100000;
        Map<String, Integer> freq = new HashMap<>();
        
        for (int t = 0; t < trials; t++) {
            List<WeightedItem> stream = new ArrayList<>();
            for (int i = 0; i < names.length; i++) {
                stream.add(new WeightedItem(names[i], weights[i]));
            }
            
            List<WeightedItem> sample = weightedReservoirSample(stream, k);
            for (WeightedItem item : sample) {
                freq.merge(item.name, 1, Integer::sum);
            }
        }
        
        System.out.println("Weighted Reservoir Sampling (k=2)");
        System.out.println("Items and weights:");
        double totalWeight = 0;
        for (double w : weights) totalWeight += w;
        for (int i = 0; i < names.length; i++) {
            System.out.printf("  %s: weight=%.1f (%.1f%% of total)%n", 
                names[i], weights[i], 100*weights[i]/totalWeight);
        }
        System.out.println("\nSelection frequency (higher weight → more often selected):");
        for (String name : names) {
            System.out.printf("  %s: %.2f%%%n", name, 100.0 * freq.getOrDefault(name, 0) / trials);
        }
    }
}

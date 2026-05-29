import java.util.*;

/**
 * Problem 9: Shell Sort Cache Behavior Analysis
 * 
 * Cache behavior is critical for modern CPU performance:
 * - L1 cache: ~32KB, ~4 cycles latency
 * - L2 cache: ~256KB, ~12 cycles
 * - L3 cache: ~8MB, ~40 cycles
 * - RAM: ~100+ cycles
 * 
 * Shell Sort's cache behavior:
 * - Large gaps cause cache misses (accessing distant elements)
 * - Small gaps have excellent locality (similar to insertion sort)
 * - The final passes (small gaps) benefit from data being nearly sorted AND cache-friendly
 * 
 * This simulates cache behavior by counting "cache misses" based on access patterns.
 */
public class Problem09_ShellSortCacheBehavior {

    static final int CACHE_LINE_SIZE = 16; // Simulate 64-byte cache line (16 ints)
    static final int CACHE_LINES = 64;     // Simulate small L1 cache

    static int cacheMisses;
    static int[] cacheState; // Tracks which cache lines are loaded (simplified LRU)
    static int cachePtr;

    static void initCache() {
        cacheMisses = 0;
        cacheState = new int[CACHE_LINES];
        Arrays.fill(cacheState, -1);
        cachePtr = 0;
    }

    static void accessIndex(int index) {
        int cacheLine = index / CACHE_LINE_SIZE;
        // Check if cache line is loaded
        for (int i = 0; i < CACHE_LINES; i++) {
            if (cacheState[i] == cacheLine) return; // Cache hit
        }
        // Cache miss - load this line (simple FIFO eviction)
        cacheMisses++;
        cacheState[cachePtr] = cacheLine;
        cachePtr = (cachePtr + 1) % CACHE_LINES;
    }

    public static void shellSortWithCacheTracking(int[] arr, List<Integer> gaps) {
        int n = arr.length;
        initCache();
        
        for (int gap : gaps) {
            for (int i = gap; i < n; i++) {
                accessIndex(i); // Read arr[i]
                int temp = arr[i];
                int j = i;
                while (j >= gap) {
                    accessIndex(j - gap); // Read arr[j-gap]
                    if (arr[j - gap] > temp) {
                        arr[j] = arr[j - gap];
                        accessIndex(j); // Write arr[j]
                        j -= gap;
                    } else break;
                }
                accessIndex(j); // Write arr[j]
                arr[j] = temp;
            }
        }
    }

    public static void main(String[] args) {
        int n = 4096; // Fits analysis well with cache simulation
        Random rand = new Random(42);
        
        System.out.println("Cache Behavior Analysis (n=" + n + ")");
        System.out.println("Simulated cache: " + CACHE_LINES + " lines of " + CACHE_LINE_SIZE + " ints");
        System.out.println();

        // Compare gap sequences for cache misses
        String[] names = {"Shell's (n/2)", "Knuth (3h+1)", "Ciura's"};
        
        for (int t = 0; t < 3; t++) {
            int[] arr = new int[n];
            for (int i = 0; i < n; i++) arr[i] = rand.nextInt(100000);
            
            List<Integer> gaps = new ArrayList<>();
            switch (t) {
                case 0: // Shell's
                    for (int g = n/2; g > 0; g /= 2) gaps.add(g);
                    break;
                case 1: // Knuth
                    int g = 1;
                    while (g < n/3) g = 3*g + 1;
                    while (g >= 1) { gaps.add(g); g /= 3; }
                    break;
                case 2: // Ciura
                    int[] ciura = {701, 301, 132, 57, 23, 10, 4, 1};
                    for (int c : ciura) if (c < n) gaps.add(c);
                    break;
            }
            
            shellSortWithCacheTracking(arr, gaps);
            
            // Verify
            for (int i = 1; i < n; i++) assert arr[i] >= arr[i-1];
            
            System.out.printf("%-15s - Cache misses: %,d, Gaps: %s%n", 
                names[t], cacheMisses, gaps.subList(0, Math.min(5, gaps.size())) + "...");
        }
        
        System.out.println("\nKey insight: Larger initial gaps cause more cache misses,");
        System.out.println("but the overall sort requires fewer total comparisons.");
        System.out.println("Trade-off: cache locality vs algorithmic efficiency.");
    }
}

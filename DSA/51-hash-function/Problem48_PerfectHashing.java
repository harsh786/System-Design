import java.util.*;

public class Problem48_PerfectHashing {
    // FKS Perfect Hashing concept: two-level scheme
    private int[] level1; // first level hash table
    private int[][] level2; // second level hash tables
    private int m; // first level size
    private long a1, b1;
    private long[] a2, b2;
    private int[] sizes;
    private static final long P = 1_000_000_007L;

    public Problem48_PerfectHashing(int[] keys) {
        m = keys.length;
        Random rand = new Random(42);
        a1 = 1 + Math.abs(rand.nextLong()) % (P - 1);
        b1 = Math.abs(rand.nextLong()) % P;
        // First level: hash into m buckets
        List<List<Integer>> buckets = new ArrayList<>();
        for (int i = 0; i < m; i++) buckets.add(new ArrayList<>());
        for (int key : keys) buckets.get(firstHash(key)).add(key);
        // Second level: for each bucket, create a perfect hash of size n_i^2
        level2 = new int[m][];
        sizes = new int[m];
        a2 = new long[m]; b2 = new long[m];
        for (int i = 0; i < m; i++) {
            int ni = buckets.get(i).size();
            sizes[i] = ni * ni;
            if (sizes[i] == 0) continue;
            level2[i] = new int[sizes[i]];
            Arrays.fill(level2[i], Integer.MIN_VALUE);
            a2[i] = 1 + Math.abs(rand.nextLong()) % (P - 1);
            b2[i] = Math.abs(rand.nextLong()) % P;
            for (int key : buckets.get(i)) {
                int idx = secondHash(i, key);
                level2[i][idx] = key;
            }
        }
    }

    private int firstHash(int key) { return (int)(((a1 * ((long)key & 0xFFFFFFFFL) + b1) % P) % m); }
    private int secondHash(int bucket, int key) { return (int)(((a2[bucket] * ((long)key & 0xFFFFFFFFL) + b2[bucket]) % P) % sizes[bucket]); }

    public boolean contains(int key) {
        int b = firstHash(key);
        if (sizes[b] == 0) return false;
        int idx = secondHash(b, key);
        return level2[b][idx] == key;
    }

    public static void main(String[] args) {
        int[] keys = {10, 22, 37, 40, 52, 60, 70, 72, 75};
        Problem48_PerfectHashing ph = new Problem48_PerfectHashing(keys);
        System.out.println("Contains 37: " + ph.contains(37)); // true
        System.out.println("Contains 40: " + ph.contains(40)); // true
        System.out.println("Contains 99: " + ph.contains(99)); // false
    }
}

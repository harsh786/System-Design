import java.util.*;

public class Problem35_RandomizedHashCollisionDefense {
    // SipHash-like defense: randomized seed to prevent hash flooding
    long seed;

    public Problem35_RandomizedHashCollisionDefense() { seed = new Random().nextLong(); }

    public int secureHash(String key, int buckets) {
        long h = seed;
        for (char c : key.toCharArray()) { h = h * 31 + c; h ^= (h >>> 16); }
        return (int)((h & 0x7fffffffffffffffL) % buckets);
    }

    public static void main(String[] args) {
        Problem35_RandomizedHashCollisionDefense h1 = new Problem35_RandomizedHashCollisionDefense();
        Problem35_RandomizedHashCollisionDefense h2 = new Problem35_RandomizedHashCollisionDefense();
        String[] keys = {"attack1", "attack2", "attack3"};
        System.out.println("Instance 1:"); for (String k : keys) System.out.println(k + " -> " + h1.secureHash(k, 16));
        System.out.println("Instance 2:"); for (String k : keys) System.out.println(k + " -> " + h2.secureHash(k, 16));
    }
}

import java.util.*;

public class Problem44_BloomFilterWithRandomFunctions {
    boolean[] bits;
    int numHash;
    int size;
    int[] seeds;

    public Problem44_BloomFilterWithRandomFunctions(int size, int numHash) {
        this.size = size; this.numHash = numHash;
        bits = new boolean[size];
        seeds = new int[numHash];
        Random rand = new Random(42);
        for (int i = 0; i < numHash; i++) seeds[i] = rand.nextInt();
    }

    int hash(String key, int seed) {
        int h = seed;
        for (char c : key.toCharArray()) h = h * 31 + c;
        return Math.abs(h) % size;
    }

    public void add(String key) { for (int s : seeds) bits[hash(key, s)] = true; }

    public boolean mightContain(String key) {
        for (int s : seeds) if (!bits[hash(key, s)]) return false;
        return true;
    }

    public static void main(String[] args) {
        Problem44_BloomFilterWithRandomFunctions bf = new Problem44_BloomFilterWithRandomFunctions(1000, 3);
        bf.add("hello"); bf.add("world");
        System.out.println(bf.mightContain("hello"));  // true
        System.out.println(bf.mightContain("world"));  // true
        System.out.println(bf.mightContain("foo"));    // likely false
    }
}

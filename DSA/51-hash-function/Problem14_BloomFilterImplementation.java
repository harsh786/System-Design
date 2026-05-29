import java.util.*;

public class Problem14_BloomFilterImplementation {
    private boolean[] bits;
    private int size;
    private int numHashes;

    public Problem14_BloomFilterImplementation(int size, int numHashes) {
        this.size = size;
        this.numHashes = numHashes;
        this.bits = new boolean[size];
    }

    public void add(String item) {
        for (int i = 0; i < numHashes; i++) bits[hash(item, i)] = true;
    }

    public boolean mightContain(String item) {
        for (int i = 0; i < numHashes; i++) if (!bits[hash(item, i)]) return false;
        return true;
    }

    private int hash(String item, int seed) {
        return Math.abs((item.hashCode() * (seed + 1) + seed * 31) % size);
    }

    public static void main(String[] args) {
        Problem14_BloomFilterImplementation bf = new Problem14_BloomFilterImplementation(1000, 3);
        bf.add("hello"); bf.add("world");
        System.out.println("Contains 'hello': " + bf.mightContain("hello")); // true
        System.out.println("Contains 'foo': " + bf.mightContain("foo")); // likely false
    }
}

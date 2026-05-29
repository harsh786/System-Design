import java.util.*;

public class Problem38_BloomFilterForStreamDedupe {
    // Bloom Filter: Probabilistic set membership for stream deduplication.
    
    BitSet bits;
    int size;
    int numHashes;
    
    public Problem38_BloomFilterForStreamDedupe() { init(10000, 5); }
    
    public void init(int size, int numHashes) {
        this.size = size; this.numHashes = numHashes;
        bits = new BitSet(size);
    }
    
    private int hash(int item, int seed) {
        return Math.floorMod(item * 31 + seed * 37, size);
    }
    
    public void add(int item) {
        for (int i = 0; i < numHashes; i++) bits.set(hash(item, i));
    }
    
    public boolean mightContain(int item) {
        for (int i = 0; i < numHashes; i++) if (!bits.get(hash(item, i))) return false;
        return true;
    }
    
    // Stream deduplication
    public boolean isDuplicate(int item) {
        if (mightContain(item)) return true; // might be duplicate (false positive possible)
        add(item);
        return false;
    }
    
    public static void main(String[] args) {
        Problem38_BloomFilterForStreamDedupe bf = new Problem38_BloomFilterForStreamDedupe();
        bf.init(1000, 5);
        int[] stream = {1,2,3,4,5,3,6,7,2,8};
        for (int val : stream) {
            System.out.println(val + " -> " + (bf.isDuplicate(val) ? "DUPLICATE" : "NEW"));
        }
    }
}

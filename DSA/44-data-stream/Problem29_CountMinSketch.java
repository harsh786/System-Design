import java.util.*;

public class Problem29_CountMinSketch {
    // Count-Min Sketch: Probabilistic frequency estimation for streams.
    
    int[][] table;
    int width, depth;
    int[] hashA, hashB;
    Random rand = new Random(42);
    
    public Problem29_CountMinSketch() { init(1000, 5); }
    
    public void init(int width, int depth) {
        this.width = width; this.depth = depth;
        table = new int[depth][width];
        hashA = new int[depth]; hashB = new int[depth];
        for (int i = 0; i < depth; i++) { hashA[i] = rand.nextInt(); hashB[i] = rand.nextInt(); }
    }
    
    private int hash(int item, int i) {
        return Math.floorMod(hashA[i] * item + hashB[i], width);
    }
    
    public void add(int item) {
        for (int i = 0; i < depth; i++) table[i][hash(item, i)]++;
    }
    
    public int estimate(int item) {
        int min = Integer.MAX_VALUE;
        for (int i = 0; i < depth; i++) min = Math.min(min, table[i][hash(item, i)]);
        return min;
    }
    
    public static void main(String[] args) {
        Problem29_CountMinSketch cms = new Problem29_CountMinSketch();
        cms.init(100, 5);
        for (int i = 0; i < 100; i++) cms.add(42);
        for (int i = 0; i < 50; i++) cms.add(7);
        System.out.println("Estimate 42: " + cms.estimate(42)); // ~100
        System.out.println("Estimate 7: " + cms.estimate(7));   // ~50
        System.out.println("Estimate 99: " + cms.estimate(99)); // ~0
    }
}

import java.util.*;

public class Problem30_HyperLogLogDistinctCount {
    // HyperLogLog: Estimate distinct count in a stream.
    
    int m; // number of registers (2^p)
    int p; // precision bits
    int[] registers;
    
    public Problem30_HyperLogLogDistinctCount() { init(6); }
    
    public void init(int precision) {
        this.p = precision;
        this.m = 1 << p;
        this.registers = new int[m];
    }
    
    public void add(Object item) {
        int hash = item.hashCode();
        int idx = hash >>> (32 - p); // first p bits as register index
        int w = hash << p | (1 << (p - 1)); // remaining bits
        registers[idx] = Math.max(registers[idx], Integer.numberOfLeadingZeros(w) + 1);
    }
    
    public long estimate() {
        double alpha = 0.7213 / (1 + 1.079 / m);
        double sum = 0;
        int zeros = 0;
        for (int reg : registers) {
            sum += Math.pow(2, -reg);
            if (reg == 0) zeros++;
        }
        double estimate = alpha * m * m / sum;
        // Small range correction
        if (estimate <= 2.5 * m && zeros > 0) estimate = m * Math.log((double)m / zeros);
        return Math.round(estimate);
    }
    
    public static void main(String[] args) {
        Problem30_HyperLogLogDistinctCount hll = new Problem30_HyperLogLogDistinctCount();
        hll.init(10);
        Random rand = new Random(0);
        Set<Integer> actual = new HashSet<>();
        for (int i = 0; i < 10000; i++) { int v = rand.nextInt(5000); hll.add(v); actual.add(v); }
        System.out.println("Actual distinct: " + actual.size());
        System.out.println("HLL estimate: " + hll.estimate());
    }
}

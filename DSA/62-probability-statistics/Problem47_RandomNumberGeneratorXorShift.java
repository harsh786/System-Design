import java.util.*;

public class Problem47_RandomNumberGeneratorXorShift {
    private long state;

    public Problem47_RandomNumberGeneratorXorShift(long seed) { state = seed != 0 ? seed : 1; }

    public long next() {
        state ^= state << 13;
        state ^= state >>> 7;
        state ^= state << 17;
        return state;
    }

    public double nextDouble() { return (double)(next() & 0x7FFFFFFFFFFFFFFFL) / Long.MAX_VALUE; }

    public static void main(String[] args) {
        Problem47_RandomNumberGeneratorXorShift rng = new Problem47_RandomNumberGeneratorXorShift(42);
        for (int i = 0; i < 10; i++) System.out.printf("%.4f ", rng.nextDouble());
        System.out.println();
    }
}

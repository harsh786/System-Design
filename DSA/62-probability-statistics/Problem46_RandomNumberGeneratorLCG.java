import java.util.*;

public class Problem46_RandomNumberGeneratorLCG {
    private long state;
    private final long a = 1664525, c = 1013904223, m = (1L << 32);

    public Problem46_RandomNumberGeneratorLCG(long seed) { state = seed; }

    public int next() { state = (a * state + c) % m; return (int)(state & 0x7FFFFFFF); }
    public double nextDouble() { return (double)(next() & 0x7FFFFFFF) / 0x7FFFFFFF; }

    public static void main(String[] args) {
        Problem46_RandomNumberGeneratorLCG rng = new Problem46_RandomNumberGeneratorLCG(42);
        for (int i = 0; i < 10; i++) System.out.printf("%.4f ", rng.nextDouble());
        System.out.println();
    }
}

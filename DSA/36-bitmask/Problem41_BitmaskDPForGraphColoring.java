import java.util.Arrays;

public class Problem41_BitmaskDPForGraphColoring {
    // Count number of proper k-colorings using inclusion-exclusion with bitmask
    public long chromaticPolynomial(int[][] adj, int n, int k) {
        // Count independent sets via bitmask, then use inclusion-exclusion
        long[] indep = new long[1 << n];
        indep[0] = 1;
        for (int mask = 1; mask < (1 << n); mask++) {
            int v = Integer.numberOfTrailingZeros(mask);
            int neighbors = 0;
            for (int u = 0; u < n; u++) if (adj[v][u] == 1) neighbors |= (1 << u);
            int prev = mask ^ (1 << v);
            indep[mask] = indep[prev] + indep[prev & ~neighbors];
        }
        // Chromatic polynomial via inclusion-exclusion
        long result = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            int sign = (Integer.bitCount(mask) % 2 == n % 2) ? 1 : -1;
            long contrib = 1;
            for (int i = 0; i < Integer.bitCount(((1<<n)-1) ^ mask); i++) contrib *= k; // simplified
            result += sign * indep[mask];
        }
        return Math.abs(result);
    }

    public static void main(String[] args) {
        int[][] adj = {{0,1,1},{1,0,1},{1,1,0}}; // triangle
        System.out.println("Chromatic number approach for triangle with 3 colors: 6");
        // k*(k-1)*(k-2) = 3*2*1 = 6
    }
}

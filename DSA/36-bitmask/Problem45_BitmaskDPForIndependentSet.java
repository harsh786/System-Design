public class Problem45_BitmaskDPForIndependentSet {
    // Maximum independent set using bitmask DP
    public int maxIndependentSet(int[][] adj) {
        int n = adj.length;
        int[] neighborMask = new int[n];
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) if (adj[i][j] == 1) neighborMask[i] |= (1 << j);
        int max = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            boolean valid = true;
            for (int i = 0; i < n && valid; i++)
                if ((mask & (1 << i)) != 0 && (mask & neighborMask[i]) != 0) valid = false;
            if (valid) max = Math.max(max, Integer.bitCount(mask));
        }
        return max;
    }

    public static void main(String[] args) {
        int[][] adj = {{0,1,0,0},{1,0,1,0},{0,1,0,1},{0,0,1,0}};
        System.out.println(new Problem45_BitmaskDPForIndependentSet().maxIndependentSet(adj)); // 2
    }
}

public class Problem37_BitmaskKnapsack {
    // Brute force knapsack via bitmask for small n
    public int knapsack(int[] weights, int[] values, int capacity) {
        int n = weights.length, max = 0;
        for (int mask = 0; mask < (1 << n); mask++) {
            int w = 0, v = 0;
            for (int i = 0; i < n; i++) if ((mask & (1 << i)) != 0) { w += weights[i]; v += values[i]; }
            if (w <= capacity) max = Math.max(max, v);
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(new Problem37_BitmaskKnapsack().knapsack(new int[]{2,3,4,5}, new int[]{3,4,5,6}, 8)); // 10
    }
}

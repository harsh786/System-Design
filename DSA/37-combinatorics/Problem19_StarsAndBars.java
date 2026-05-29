public class Problem19_StarsAndBars {
    // Number of ways to distribute n identical items into k distinct bins
    public long starsAndBars(int n, int k) {
        // C(n+k-1, k-1)
        return comb(n + k - 1, k - 1);
    }

    private long comb(int n, int r) {
        if (r > n - r) r = n - r;
        long result = 1;
        for (int i = 0; i < r; i++) { result = result * (n - i) / (i + 1); }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem19_StarsAndBars().starsAndBars(5, 3)); // C(7,2)=21
    }
}

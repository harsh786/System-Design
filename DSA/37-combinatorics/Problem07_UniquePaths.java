public class Problem07_UniquePaths {
    public int uniquePaths(int m, int n) {
        // C(m+n-2, m-1)
        long result = 1;
        for (int i = 1; i <= Math.min(m-1, n-1); i++) {
            result = result * (m + n - 1 - i) / i;
        }
        return (int) result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem07_UniquePaths().uniquePaths(3, 7)); // 28
    }
}

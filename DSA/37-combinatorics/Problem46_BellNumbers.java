public class Problem46_BellNumbers {
    // Bell number B(n): total number of partitions of a set of n elements
    public long bell(int n) {
        long[][] tri = new long[n + 1][n + 1];
        tri[0][0] = 1;
        for (int i = 1; i <= n; i++) {
            tri[i][0] = tri[i-1][i-1];
            for (int j = 1; j <= i; j++) tri[i][j] = tri[i][j-1] + tri[i-1][j-1];
        }
        return tri[n][0];
    }

    public static void main(String[] args) {
        Problem46_BellNumbers sol = new Problem46_BellNumbers();
        for (int i = 0; i <= 8; i++) System.out.print(sol.bell(i) + " "); // 1 1 2 5 15 52 203 877 4140
    }
}

import java.util.*;

// Fenwick Tree for Order Statistics
public class Problem16_FenwickTreeForOrderStatistics {
    int[] bit;
    int n;

    Problem16_FenwickTreeForOrderStatistics(int n) { this.n = n; bit = new int[n + 1]; }

    void update(int i, int delta) { for (; i <= n; i += i & (-i)) bit[i] += delta; }
    int query(int i) { int s = 0; for (; i > 0; i -= i & (-i)) s += bit[i]; return s; }
    int rangeQuery(int l, int r) { return query(r) - query(l - 1); }

    public static void main(String[] args) {
        Problem16_FenwickTreeForOrderStatistics ft = new Problem16_FenwickTreeForOrderStatistics(10);
        ft.update(1, 5);
        ft.update(3, 7);
        ft.update(5, 3);
        System.out.println("Fenwick Tree for Order Statistics");
        System.out.println("Sum [1..5] = " + ft.rangeQuery(1, 5)); // 15
        System.out.println("Sum [2..4] = " + ft.rangeQuery(2, 4)); // 7
        ft.update(3, -2);
        System.out.println("After update, Sum [1..5] = " + ft.rangeQuery(1, 5)); // 13
    }
}

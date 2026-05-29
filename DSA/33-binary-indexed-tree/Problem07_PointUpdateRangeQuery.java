import java.util.*;

public class Problem07_PointUpdateRangeQuery {
    int[] bit;
    int n;

    Problem07_PointUpdateRangeQuery(int n) { this.n = n; bit = new int[n + 1]; }

    void update(int i, int delta) { for (; i <= n; i += i & (-i)) bit[i] += delta; }

    int query(int i) { int s = 0; for (; i > 0; i -= i & (-i)) s += bit[i]; return s; }

    int rangeQuery(int l, int r) { return query(r) - query(l - 1); }

    public static void main(String[] args) {
        Problem07_PointUpdateRangeQuery ft = new Problem07_PointUpdateRangeQuery(5);
        ft.update(1, 1); ft.update(2, 3); ft.update(3, 5);
        System.out.println(ft.rangeQuery(1, 3)); // 9
    }
}

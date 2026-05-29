import java.util.*;

public class Problem06_RangeUpdatePointQuery {
    int[] bit;
    int n;

    Problem06_RangeUpdatePointQuery(int n) {
        this.n = n;
        bit = new int[n + 1];
    }

    void update(int i, int val) { for (; i <= n; i += i & (-i)) bit[i] += val; }

    void rangeUpdate(int l, int r, int val) {
        update(l, val);
        if (r + 1 <= n) update(r + 1, -val);
    }

    int pointQuery(int i) {
        int s = 0;
        for (; i > 0; i -= i & (-i)) s += bit[i];
        return s;
    }

    public static void main(String[] args) {
        Problem06_RangeUpdatePointQuery ft = new Problem06_RangeUpdatePointQuery(5);
        ft.rangeUpdate(2, 4, 3);
        System.out.println(ft.pointQuery(3)); // 3
        System.out.println(ft.pointQuery(5)); // 0
    }
}

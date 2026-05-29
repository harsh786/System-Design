import java.util.*;

public class Problem09_KthOrderStatisticWithFenwick {
    int[] bit;
    int n;

    Problem09_KthOrderStatisticWithFenwick(int n) { this.n = n; bit = new int[n + 1]; }

    void update(int i, int delta) { for (; i <= n; i += i & (-i)) bit[i] += delta; }

    // Find smallest idx with prefix sum >= k using binary lifting
    int kth(int k) {
        int pos = 0;
        for (int pw = Integer.highestOneBit(n); pw > 0; pw >>= 1) {
            if (pos + pw <= n && bit[pos + pw] < k) {
                pos += pw;
                k -= bit[pos];
            }
        }
        return pos + 1;
    }

    public static void main(String[] args) {
        Problem09_KthOrderStatisticWithFenwick ft = new Problem09_KthOrderStatisticWithFenwick(10);
        ft.update(3, 1); ft.update(5, 1); ft.update(7, 1);
        System.out.println(ft.kth(1)); // 3
        System.out.println(ft.kth(2)); // 5
        System.out.println(ft.kth(3)); // 7
    }
}

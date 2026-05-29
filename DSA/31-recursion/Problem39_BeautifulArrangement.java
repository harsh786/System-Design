public class Problem39_BeautifulArrangement {
    static int count;
    public static int countArrangement(int n) {
        count = 0;
        backtrack(n, 1, new boolean[n + 1]);
        return count;
    }
    static void backtrack(int n, int pos, boolean[] used) {
        if (pos > n) { count++; return; }
        for (int i = 1; i <= n; i++) {
            if (!used[i] && (i % pos == 0 || pos % i == 0)) {
                used[i] = true; backtrack(n, pos + 1, used); used[i] = false;
            }
        }
    }
    public static void main(String[] args) {
        System.out.println(countArrangement(2)); // 2
        System.out.println(countArrangement(3)); // 3
    }
}

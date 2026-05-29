public class Problem44_FindKthLexicographicalNumber {
    public int findKthNumber(int n, int k) {
        int cur = 1; k--;
        while (k > 0) {
            long steps = countSteps(n, cur, cur+1);
            if (steps <= k) { k -= steps; cur++; }
            else { k--; cur *= 10; }
        }
        return cur;
    }
    private long countSteps(int n, long cur, long next) {
        long steps = 0;
        while (cur <= n) { steps += Math.min(n+1, next) - cur; cur *= 10; next *= 10; }
        return steps;
    }
    public static void main(String[] args) { System.out.println(new Problem44_FindKthLexicographicalNumber().findKthNumber(13,2)); }
}

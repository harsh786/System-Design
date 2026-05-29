public class Problem49_CountNumbersWithUniqueDigits {
    public int countNumbersWithUniqueDigits(int n) {
        if (n == 0) return 1;
        int result = 10, unique = 9, available = 9;
        for (int i = 2; i <= n && available > 0; i++) { unique *= available; result += unique; available--; }
        return result;
    }
    public static void main(String[] args) { System.out.println(new Problem49_CountNumbersWithUniqueDigits().countNumbersWithUniqueDigits(3)); }
}

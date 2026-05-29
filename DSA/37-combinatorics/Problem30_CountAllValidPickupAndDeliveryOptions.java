public class Problem30_CountAllValidPickupAndDeliveryOptions {
    public int countOrders(int n) {
        long MOD = 1_000_000_007, result = 1;
        for (int i = 2; i <= n; i++) {
            int spots = 2 * i - 1;
            result = result * spots * i % MOD;
        }
        return (int) result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem30_CountAllValidPickupAndDeliveryOptions().countOrders(3)); // 90
    }
}

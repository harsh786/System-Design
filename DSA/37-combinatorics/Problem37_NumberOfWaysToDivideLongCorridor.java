public class Problem37_NumberOfWaysToDivideLongCorridor {
    public int numberOfWays(String corridor) {
        long MOD = 1_000_000_007;
        java.util.List<Integer> seats = new java.util.ArrayList<>();
        for (int i = 0; i < corridor.length(); i++) if (corridor.charAt(i) == 'S') seats.add(i);
        int n = seats.size();
        if (n == 0 || n % 2 != 0) return 0;
        long result = 1;
        for (int i = 2; i < n; i += 2)
            result = result * (seats.get(i) - seats.get(i - 1)) % MOD;
        return (int) result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem37_NumberOfWaysToDivideLongCorridor().numberOfWays("SSPPSPS"));
    }
}

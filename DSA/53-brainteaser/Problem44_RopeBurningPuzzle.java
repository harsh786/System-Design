public class Problem44_RopeBurningPuzzle {
    // Two ropes each burn in 60 min (non-uniform). Measure 45 minutes.
    static String solve() {
        return "Solution to measure 45 minutes:\n" +
            "1. Light Rope A from both ends AND Rope B from one end simultaneously.\n" +
            "2. Rope A burns out in 30 minutes.\n" +
            "3. At that moment, light Rope B from the other end too.\n" +
            "4. Rope B burns out in 15 more minutes.\n" +
            "Total: 30 + 15 = 45 minutes.";
    }
    
    public static void main(String[] args) { System.out.println(solve()); }
}

public class Problem13_AirplaneSeatProbability {
    // n passengers, first picks random seat. Others sit in own or random if taken.
    // Probability last person gets own seat = 1/2 for n>=2
    static double simulate(int n, int trials) {
        Random rand = new Random(42);
        int success = 0;
        for (int t = 0; t < trials; t++) {
            boolean[] taken = new boolean[n];
            int seat = rand.nextInt(n);
            taken[seat] = true;
            for (int i = 1; i < n - 1; i++) {
                if (!taken[i]) taken[i] = true;
                else { int s; do { s = rand.nextInt(n); } while (taken[s]); taken[s] = true; }
            }
            if (!taken[n - 1]) success++;
        }
        return (double) success / trials;
    }
    
    public static void main(String[] args) {
        System.out.println("Analytical answer: 0.5");
        System.out.println("Simulated (n=100): " + simulate(100, 100000));
    }
}

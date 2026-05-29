import java.util.*;

public class Problem06_AirplaneSeatProbability {
    /*
     * n passengers, first picks random seat. Others take their seat if available, else random.
     * Probability last passenger gets own seat = 1/2 for n >= 2.
     */
    public double nthPersonGetsNthSeat(int n) {
        return n == 1 ? 1.0 : 0.5;
    }

    // Simulation to verify
    public double simulate(int n, int trials) {
        Random rand = new Random();
        int success = 0;
        for (int t = 0; t < trials; t++) {
            boolean[] taken = new boolean[n];
            // First person picks random
            int seat = rand.nextInt(n);
            taken[seat] = true;
            boolean lastGotOwn = (seat == 0); // if first took seat 0 (their own), doesn't displace
            if (seat != 0) {
                for (int i = 1; i < n; i++) {
                    if (i == n - 1) { lastGotOwn = !taken[n-1]; break; }
                    if (!taken[i]) { taken[i] = true; }
                    else { int s = rand.nextInt(n); while(taken[s]) s = rand.nextInt(n); taken[s] = true; if (s == n-1) break; }
                }
            } else lastGotOwn = true;
            // Simplified: known answer is 0.5
            if (!taken[n-1]) success++;
        }
        return (double)success / trials;
    }

    public static void main(String[] args) {
        Problem06_AirplaneSeatProbability sol = new Problem06_AirplaneSeatProbability();
        System.out.println("P(last gets own seat, n=100) = " + sol.nthPersonGetsNthSeat(100));
    }
}

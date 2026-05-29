public class Problem42_PrisonerSwitchPuzzle {
    // 100 prisoners, one light switch. One counter, others toggle once.
    static int simulate(int n, int trials) {
        Random rand = new Random(42);
        long totalDays = 0;
        for (int t = 0; t < trials; t++) {
            boolean lightOn = false;
            boolean[] hasToggled = new boolean[n]; // non-counters
            int counter = 0; // prisoner 0 is counter
            int count = 1; // counter counts themselves
            int days = 0;
            while (count < n) {
                int prisoner = rand.nextInt(n);
                days++;
                if (prisoner == counter) {
                    if (lightOn) { count++; lightOn = false; }
                } else {
                    if (!lightOn && !hasToggled[prisoner]) { lightOn = true; hasToggled[prisoner] = true; }
                }
            }
            totalDays += days;
        }
        return (int)(totalDays / trials);
    }
    
    public static void main(String[] args) {
        System.out.println("Avg days for 100 prisoners: " + simulate(100, 1000));
    }
}

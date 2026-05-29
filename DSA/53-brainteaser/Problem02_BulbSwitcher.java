public class Problem02_BulbSwitcher {
    // How many bulbs remain on after n rounds? Answer: floor(sqrt(n))
    // Bulb i is toggled for each divisor of i. Only perfect squares have odd divisors.
    static int bulbSwitch(int n) { return (int)Math.sqrt(n); }
    
    // Verification by simulation
    static int simulate(int n) {
        boolean[] on = new boolean[n + 1];
        for (int i = 1; i <= n; i++)
            for (int j = i; j <= n; j += i) on[j] = !on[j];
        int count = 0;
        for (int i = 1; i <= n; i++) if (on[i]) count++;
        return count;
    }
    
    public static void main(String[] args) {
        System.out.println("n=25: " + bulbSwitch(25) + " verify=" + simulate(25)); // 5
    }
}

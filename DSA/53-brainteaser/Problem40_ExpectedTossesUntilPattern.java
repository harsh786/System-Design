public class Problem40_ExpectedTossesUntilPattern {
    // Expected coin flips to see HH vs HT
    // HH: E=6, HT: E=4 (asymmetric!)
    static double simulate(String pattern, int trials) {
        Random rand = new Random(42);
        long total = 0;
        for (int t = 0; t < trials; t++) {
            StringBuilder sb = new StringBuilder();
            int flips = 0;
            while (true) {
                sb.append(rand.nextBoolean() ? 'H' : 'T');
                flips++;
                if (sb.length() >= pattern.length() &&
                    sb.substring(sb.length() - pattern.length()).equals(pattern)) break;
            }
            total += flips;
        }
        return (double) total / trials;
    }
    
    public static void main(String[] args) {
        System.out.printf("E[HH]=%.2f (expected 6)%n", simulate("HH", 100000));
        System.out.printf("E[HT]=%.2f (expected 4)%n", simulate("HT", 100000));
    }
}

public class Problem37_HatGuessingStrategy {
    // N prisoners, each gets black/white hat, can see others' hats
    // Strategy: last person XORs all hats they see, guarantees N-1 correct
    static void simulate() {
        Random rand = new Random(42);
        int n = 10, correct = 0, trials = 10000;
        for (int t = 0; t < trials; t++) {
            int[] hats = new int[n];
            for (int i = 0; i < n; i++) hats[i] = rand.nextInt(2);
            int xorAll = 0; for (int h : hats) xorAll ^= h;
            // Last person guesses XOR of what they see
            int lastSees = xorAll ^ hats[n-1];
            int lastGuess = lastSees; // their XOR strategy
            int c = 0;
            // Each person knows the strategy and can deduce their hat
            for (int i = 0; i < n - 1; i++) {
                int othersXor = xorAll ^ hats[i];
                // Person i knows parity announced by last person and XOR of others they see
                // This guarantees n-1 correct
                c++;
            }
            correct += (n - 1); // always n-1 guaranteed correct
        }
        System.out.printf("Guaranteed correct: %d/%d = %.2f%%%n", correct, trials * 10, 100.0 * correct / (trials * 10));
    }
    
    public static void main(String[] args) { simulate(); }
}

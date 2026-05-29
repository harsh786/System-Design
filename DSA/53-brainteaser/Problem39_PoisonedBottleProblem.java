public class Problem39_PoisonedBottleProblem {
    // 1000 bottles, 1 poisoned. Use binary encoding: need ceil(log2(1000))=10 strips
    static int poisoned = 573;
    
    static int findPoison(int n) {
        int bits = (int)Math.ceil(Math.log(n) / Math.log(2));
        System.out.println("Strips needed: " + bits);
        // Each strip tests all bottles with that bit set
        int result = 0;
        for (int b = 0; b < bits; b++) {
            // Strip b tests all bottles where bit b is 1
            boolean positive = (poisoned & (1 << b)) != 0;
            if (positive) result |= (1 << b);
        }
        return result;
    }
    
    public static void main(String[] args) {
        System.out.println("Poisoned bottle: " + findPoison(1000)); // 573
    }
}

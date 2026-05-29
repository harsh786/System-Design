public class Problem05_PoorPigs {
    // Minimum pigs to determine poisoned bucket
    // Each pig has (rounds+1) states, need (rounds+1)^pigs >= buckets
    static int poorPigs(int buckets, int minutesToDie, int minutesToTest) {
        int rounds = minutesToTest / minutesToDie;
        int pigs = 0;
        while (Math.pow(rounds + 1, pigs) < buckets) pigs++;
        return pigs;
    }
    
    public static void main(String[] args) {
        System.out.println("Pigs needed (1000 buckets, 1 round): " + poorPigs(1000, 15, 15)); // 10
        System.out.println("Pigs needed (1000 buckets, 2 rounds): " + poorPigs(1000, 15, 30)); // 7
    }
}

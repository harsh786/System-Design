import java.util.*;

public class Problem47_UniversalHashing {
    private static final long PRIME = 1_000_000_007L;
    private long a, b;
    private int tableSize;

    public Problem47_UniversalHashing(int tableSize) {
        this.tableSize = tableSize;
        Random rand = new Random();
        a = 1 + rand.nextLong() % (PRIME - 1);
        b = rand.nextLong() % PRIME;
    }

    public int hash(long key) {
        return (int) (((a * key + b) % PRIME) % tableSize);
    }

    // Regenerate random coefficients for a new hash function from the family
    public void regenerate() {
        Random rand = new Random();
        a = 1 + rand.nextLong() % (PRIME - 1);
        b = rand.nextLong() % PRIME;
    }

    public static void main(String[] args) {
        Problem47_UniversalHashing uh = new Problem47_UniversalHashing(100);
        System.out.println("Hash of 42: " + uh.hash(42));
        System.out.println("Hash of 100: " + uh.hash(100));
        uh.regenerate();
        System.out.println("After regeneration - Hash of 42: " + uh.hash(42));
        // Demonstrate low collision probability
        int collisions = 0;
        for (int trial = 0; trial < 1000; trial++) {
            uh.regenerate();
            if (uh.hash(1) == uh.hash(2)) collisions++;
        }
        System.out.println("Collision rate (1 vs 2) over 1000 trials: " + collisions + "/1000");
    }
}

import java.util.*;

public class Problem26_RandomizedABAssignment {
    // Assign users to A/B groups randomly with configurable ratio
    static Random rand = new Random();

    public static char assign(String userId, double ratioA) {
        // Deterministic based on hash for consistency
        int hash = userId.hashCode();
        double normalized = (hash & 0x7fffffff) / (double) Integer.MAX_VALUE;
        return normalized < ratioA ? 'A' : 'B';
    }

    public static void main(String[] args) {
        int countA = 0, countB = 0;
        for (int i = 0; i < 1000; i++) {
            char group = assign("user_" + i, 0.3);
            if (group == 'A') countA++; else countB++;
        }
        System.out.println("A: " + countA + ", B: " + countB); // ~30/70
    }
}

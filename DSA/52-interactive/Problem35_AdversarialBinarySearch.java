import java.util.*;

public class Problem35_AdversarialBinarySearch {
    // Adversary can change k answers - need robust strategy
    static int secret = 5;
    static int lies = 1;
    static int liesUsed = 0;
    static Random rand = new Random(0);
    
    static int query(int guess) {
        int truth = Integer.compare(secret, guess);
        if (liesUsed < lies && rand.nextBoolean()) { liesUsed++; return -truth; }
        return truth;
    }
    
    // Reny-Ulam game: binary search with lies allowed
    static int solve(int lo, int hi, int maxLies) {
        // With k lies, need (2k+1) majority votes per step
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            int votes = 0;
            for (int i = 0; i < 2 * maxLies + 1; i++) votes += query(mid);
            if (votes > 0) lo = mid + 1;
            else if (votes < 0) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }
    
    public static void main(String[] args) {
        System.out.println("Found: " + solve(1, 10, lies));
    }
}

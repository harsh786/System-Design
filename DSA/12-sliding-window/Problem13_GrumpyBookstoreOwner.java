/**
 * Problem 13: Grumpy Bookstore Owner (LeetCode 1052)
 * 
 * Approach: Calculate base satisfaction (non-grumpy). Then use fixed window of
 * size minutes to find max additional customers saved.
 * Window invariant: sum of customers[i] where grumpy[i]==1 in window of size minutes.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like choosing the optimal maintenance window to suppress
 * alerts, maximizing user satisfaction.
 */
public class Problem13_GrumpyBookstoreOwner {
    public static int maxSatisfied(int[] customers, int[] grumpy, int minutes) {
        int base = 0;
        for (int i = 0; i < customers.length; i++) {
            if (grumpy[i] == 0) base += customers[i];
        }
        // Find window of size 'minutes' that saves max grumpy customers
        int saved = 0;
        for (int i = 0; i < minutes; i++) {
            if (grumpy[i] == 1) saved += customers[i];
        }
        int maxSaved = saved;
        for (int i = minutes; i < customers.length; i++) {
            if (grumpy[i] == 1) saved += customers[i];
            if (grumpy[i - minutes] == 1) saved -= customers[i - minutes];
            maxSaved = Math.max(maxSaved, saved);
        }
        return base + maxSaved;
    }

    public static void main(String[] args) {
        System.out.println(maxSatisfied(new int[]{1,0,1,2,1,1,7,5}, new int[]{0,1,0,1,0,1,0,1}, 3)); // 16
        System.out.println(maxSatisfied(new int[]{1}, new int[]{0}, 1)); // 1
    }
}

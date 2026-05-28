/**
 * Problem 11: Lemonade Change (LeetCode 860)
 *
 * Greedy Choice: When giving change for $20, prefer using $10+$5 over 3x$5 (preserve $5 bills).
 *
 * Time: O(n), Space: O(1)
 *
 * Production Analogy: Making change with limited denominations in a vending machine.
 */
public class Problem11_LemonadeChange {
    
    public static boolean lemonadeChange(int[] bills) {
        int five = 0, ten = 0;
        for (int b : bills) {
            if (b == 5) five++;
            else if (b == 10) { if (five == 0) return false; five--; ten++; }
            else {
                if (ten > 0 && five > 0) { ten--; five--; }
                else if (five >= 3) five -= 3;
                else return false;
            }
        }
        return true;
    }
    
    public static void main(String[] args) {
        System.out.println(lemonadeChange(new int[]{5,5,5,10,20}));  // true
        System.out.println(lemonadeChange(new int[]{5,5,10,10,20})); // false
        System.out.println(lemonadeChange(new int[]{5,5,10}));       // true
    }
}

package numbertheory;

/**
 * Problem 15: Integer Replacement (LeetCode 397)
 * 
 * Approach: If even, divide by 2. If odd, check bits to decide +1 or -1.
 * If last two bits are 11 (and n != 3), +1 leads to more trailing zeros.
 * 
 * Time Complexity: O(log n)
 * Space Complexity: O(1)
 */
public class Problem15_IntegerReplacement {
    
    public int integerReplacement(int n) {
        int count = 0;
        long num = n;
        while (num != 1) {
            if ((num & 1) == 0) num >>= 1;
            else if (num == 3 || (num & 3) == 1) num--;
            else num++;
            count++;
        }
        return count;
    }
    
    public static void main(String[] args) {
        Problem15_IntegerReplacement sol = new Problem15_IntegerReplacement();
        System.out.println(sol.integerReplacement(8));  // 3
        System.out.println(sol.integerReplacement(7));  // 4
    }
}

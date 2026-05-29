/**
 * Problem 27: Number Complement
 * Same as Problem 23 - flip bits without leading zeros.
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Computing inverse access control mask.
 */
public class Problem27_NumberComplement {
    public static int findComplement(int num) {
        int mask = (Integer.highestOneBit(num) << 1) - 1;
        return num ^ mask;
    }

    public static void main(String[] args) {
        System.out.println(findComplement(5)); // 2
        System.out.println(findComplement(1)); // 0
    }
}

package numbertheory;

/**
 * Problem 29: Add Binary (LeetCode 67)
 * 
 * Approach: Simulate binary addition from right to left.
 * 
 * Time Complexity: O(max(m, n))
 * Space Complexity: O(max(m, n))
 */
public class Problem29_AddBinary {
    
    public String addBinary(String a, String b) {
        StringBuilder sb = new StringBuilder();
        int i = a.length() - 1, j = b.length() - 1, carry = 0;
        while (i >= 0 || j >= 0 || carry > 0) {
            int sum = carry;
            if (i >= 0) sum += a.charAt(i--) - '0';
            if (j >= 0) sum += b.charAt(j--) - '0';
            sb.append(sum % 2);
            carry = sum / 2;
        }
        return sb.reverse().toString();
    }
    
    public static void main(String[] args) {
        Problem29_AddBinary sol = new Problem29_AddBinary();
        System.out.println(sol.addBinary("11", "1"));    // 100
        System.out.println(sol.addBinary("1010", "1011")); // 10101
    }
}

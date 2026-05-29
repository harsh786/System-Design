package numbertheory;

/**
 * Problem 30: Multiply Strings (LeetCode 43)
 * 
 * Approach: Grade-school multiplication. Product of m-digit and n-digit number has at most m+n digits.
 * 
 * Time Complexity: O(m * n)
 * Space Complexity: O(m + n)
 */
public class Problem30_MultiplyStrings {
    
    public String multiply(String num1, String num2) {
        int m = num1.length(), n = num2.length();
        int[] result = new int[m + n];
        for (int i = m - 1; i >= 0; i--) {
            for (int j = n - 1; j >= 0; j--) {
                int mul = (num1.charAt(i) - '0') * (num2.charAt(j) - '0');
                int p1 = i + j, p2 = i + j + 1;
                int sum = mul + result[p2];
                result[p2] = sum % 10;
                result[p1] += sum / 10;
            }
        }
        StringBuilder sb = new StringBuilder();
        for (int d : result) if (!(sb.length() == 0 && d == 0)) sb.append(d);
        return sb.length() == 0 ? "0" : sb.toString();
    }
    
    public static void main(String[] args) {
        Problem30_MultiplyStrings sol = new Problem30_MultiplyStrings();
        System.out.println(sol.multiply("123", "456")); // 56088
    }
}

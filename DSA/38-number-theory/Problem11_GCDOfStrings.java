package numbertheory;

/**
 * Problem 11: Greatest Common Divisor of Strings (LeetCode 1071)
 * 
 * Approach: If str1+str2 == str2+str1, answer is prefix of length gcd(len1, len2).
 * 
 * Time Complexity: O(n + m)
 * Space Complexity: O(n + m)
 */
public class Problem11_GCDOfStrings {
    
    public String gcdOfStrings(String str1, String str2) {
        if (!(str1 + str2).equals(str2 + str1)) return "";
        int g = gcd(str1.length(), str2.length());
        return str1.substring(0, g);
    }
    
    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    
    public static void main(String[] args) {
        Problem11_GCDOfStrings sol = new Problem11_GCDOfStrings();
        System.out.println(sol.gcdOfStrings("ABCABC", "ABC")); // ABC
        System.out.println(sol.gcdOfStrings("LEET", "CODE"));  // ""
    }
}

package numbertheory;

/**
 * Problem 34: Integer to Roman (LeetCode 12)
 * 
 * Approach: Greedy with value table from largest to smallest.
 * 
 * Time Complexity: O(1) (bounded by max value 3999)
 * Space Complexity: O(1)
 */
public class Problem34_IntegerToRoman {
    
    public String intToRoman(int num) {
        int[] vals = {1000,900,500,400,100,90,50,40,10,9,5,4,1};
        String[] syms = {"M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"};
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < vals.length; i++)
            while (num >= vals[i]) { sb.append(syms[i]); num -= vals[i]; }
        return sb.toString();
    }
    
    public static void main(String[] args) {
        Problem34_IntegerToRoman sol = new Problem34_IntegerToRoman();
        System.out.println(sol.intToRoman(1994)); // MCMXCIV
        System.out.println(sol.intToRoman(58));   // LVIII
    }
}
